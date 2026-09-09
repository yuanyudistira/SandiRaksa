"""
NER Batch Processor.

Provides efficient batch processing for NER inference with:
- Memory-aware batching
- Progress tracking
- Parallel document processing
- Text chunking for long documents
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Iterator

from sandiraksa.detection.ner.base import (
    NERConfig,
    NERPrediction,
    NERProvider,
    NERResult,
)

logger = logging.getLogger(__name__)


@dataclass
class BatchConfig:
    """
    Configuration for batch processing.

    Attributes:
        batch_size: Number of texts per batch
        max_text_length: Maximum text length before chunking
        chunk_overlap: Overlap between chunks (characters)
        max_memory_mb: Approximate memory limit for batching
        show_progress: Whether to report progress
    """

    batch_size: int = 32
    max_text_length: int = 512
    chunk_overlap: int = 50
    max_memory_mb: int = 512
    show_progress: bool = True

    def __post_init__(self):
        """Validate configuration."""
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.max_text_length < 100:
            raise ValueError("max_text_length must be >= 100")
        if self.chunk_overlap >= self.max_text_length:
            raise ValueError("chunk_overlap must be < max_text_length")


@dataclass
class BatchProgress:
    """Progress tracking for batch processing."""

    total_texts: int = 0
    processed_texts: int = 0
    total_batches: int = 0
    processed_batches: int = 0
    total_entities: int = 0
    start_time: float = field(default_factory=time.perf_counter)

    @property
    def progress_percent(self) -> float:
        """Get progress as percentage."""
        if self.total_texts == 0:
            return 100.0
        return (self.processed_texts / self.total_texts) * 100

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        return time.perf_counter() - self.start_time

    @property
    def texts_per_second(self) -> float:
        """Get processing rate."""
        elapsed = self.elapsed_seconds
        if elapsed == 0:
            return 0.0
        return self.processed_texts / elapsed

    @property
    def estimated_remaining_seconds(self) -> float:
        """Estimate remaining time."""
        rate = self.texts_per_second
        if rate == 0:
            return 0.0
        remaining = self.total_texts - self.processed_texts
        return remaining / rate


@dataclass
class ChunkedText:
    """A text that has been split into chunks."""

    original_text: str
    original_index: int
    chunks: list[str] = field(default_factory=list)
    chunk_offsets: list[int] = field(default_factory=list)


class NERBatchProcessor:
    """
    Efficient batch processor for NER inference.

    Handles:
    - Batching texts for efficient GPU/CPU utilization
    - Chunking long texts with overlap
    - Merging results from chunks
    - Progress tracking
    - Memory-aware processing

    Usage:
        processor = NERBatchProcessor(provider)
        results = processor.process(texts)

        # With progress callback
        def on_progress(p):
            print(f"Progress: {p.progress_percent:.1f}%")

        results = processor.process(texts, progress_callback=on_progress)
    """

    def __init__(
        self,
        provider: NERProvider,
        batch_config: BatchConfig | None = None,
        ner_config: NERConfig | None = None,
    ):
        """
        Initialize batch processor.

        Args:
            provider: NER provider to use
            batch_config: Batch processing configuration
            ner_config: NER inference configuration
        """
        self._provider = provider
        self._batch_config = batch_config or BatchConfig()
        self._ner_config = ner_config or NERConfig()

    def process(
        self,
        texts: list[str],
        progress_callback: Callable[[BatchProgress], None] | None = None,
    ) -> list[NERResult]:
        """
        Process a list of texts.

        Args:
            texts: List of texts to process
            progress_callback: Optional callback for progress updates

        Returns:
            List of NERResult, one per input text
        """
        if not texts:
            return []

        # Initialize progress
        progress = BatchProgress(
            total_texts=len(texts),
            total_batches=self._calculate_batch_count(texts),
        )

        # Chunk long texts
        chunked_texts = self._chunk_texts(texts)

        # Process in batches
        all_chunk_results: list[tuple[int, int, NERResult]] = []

        for batch in self._iter_batches(chunked_texts):
            batch_texts = [item[2] for item in batch]  # (orig_idx, chunk_idx, text)

            # Run NER on batch
            batch_results = self._provider.predict(batch_texts, self._ner_config)

            # Store results with indices
            for (orig_idx, chunk_idx, _), result in zip(batch, batch_results):
                all_chunk_results.append((orig_idx, chunk_idx, result))
                progress.total_entities += result.entity_count

            # Update progress
            progress.processed_batches += 1
            progress.processed_texts = min(
                progress.processed_texts + len(batch),
                progress.total_texts,
            )

            if progress_callback:
                progress_callback(progress)

        # Merge chunk results back to original texts
        results = self._merge_chunk_results(texts, chunked_texts, all_chunk_results)

        return results

    def process_stream(
        self,
        texts: Iterator[str],
        progress_callback: Callable[[BatchProgress], None] | None = None,
    ) -> Iterator[NERResult]:
        """
        Process texts as a stream (lazy evaluation).

        Useful for very large datasets that don't fit in memory.

        Args:
            texts: Iterator of texts
            progress_callback: Optional progress callback

        Yields:
            NERResult for each text
        """
        progress = BatchProgress()
        batch_texts: list[str] = []
        batch_indices: list[int] = []
        current_index = 0

        for text in texts:
            progress.total_texts += 1
            batch_texts.append(text)
            batch_indices.append(current_index)
            current_index += 1

            if len(batch_texts) >= self._batch_config.batch_size:
                # Process batch
                results = self._provider.predict(batch_texts, self._ner_config)

                for result in results:
                    progress.processed_texts += 1
                    progress.total_entities += result.entity_count
                    yield result

                if progress_callback:
                    progress_callback(progress)

                batch_texts = []
                batch_indices = []

        # Process remaining texts
        if batch_texts:
            results = self._provider.predict(batch_texts, self._ner_config)
            for result in results:
                progress.processed_texts += 1
                progress.total_entities += result.entity_count
                yield result

            if progress_callback:
                progress_callback(progress)

    def _chunk_texts(self, texts: list[str]) -> list[ChunkedText]:
        """Split long texts into chunks."""
        chunked = []
        max_len = self._batch_config.max_text_length
        overlap = self._batch_config.chunk_overlap

        for idx, text in enumerate(texts):
            if len(text) <= max_len:
                # No chunking needed
                chunked.append(
                    ChunkedText(
                        original_text=text,
                        original_index=idx,
                        chunks=[text],
                        chunk_offsets=[0],
                    )
                )
            else:
                # Split into chunks
                chunks = []
                offsets = []
                pos = 0

                while pos < len(text):
                    end = min(pos + max_len, len(text))

                    # Try to break at word boundary
                    if end < len(text):
                        # Look for last space within chunk
                        last_space = text.rfind(" ", pos, end)
                        if last_space > pos + max_len // 2:
                            end = last_space + 1

                    chunks.append(text[pos:end])
                    offsets.append(pos)

                    # Move position (with overlap)
                    pos = end - overlap if end < len(text) else end

                chunked.append(
                    ChunkedText(
                        original_text=text,
                        original_index=idx,
                        chunks=chunks,
                        chunk_offsets=offsets,
                    )
                )

        return chunked

    def _iter_batches(
        self,
        chunked_texts: list[ChunkedText],
    ) -> Iterator[list[tuple[int, int, str]]]:
        """
        Iterate over batches of (original_index, chunk_index, text).
        """
        batch: list[tuple[int, int, str]] = []
        batch_size = self._batch_config.batch_size

        for ct in chunked_texts:
            for chunk_idx, chunk in enumerate(ct.chunks):
                batch.append((ct.original_index, chunk_idx, chunk))

                if len(batch) >= batch_size:
                    yield batch
                    batch = []

        if batch:
            yield batch

    def _merge_chunk_results(
        self,
        original_texts: list[str],
        chunked_texts: list[ChunkedText],
        chunk_results: list[tuple[int, int, NERResult]],
    ) -> list[NERResult]:
        """
        Merge chunk results back to original texts.

        Handles:
        - Adjusting offsets for chunks
        - Deduplicating entities in overlapping regions
        """
        # Group results by original index
        results_by_orig: dict[int, list[tuple[int, NERResult]]] = {}
        for orig_idx, chunk_idx, result in chunk_results:
            if orig_idx not in results_by_orig:
                results_by_orig[orig_idx] = []
            results_by_orig[orig_idx].append((chunk_idx, result))

        # Build final results
        final_results: list[NERResult] = []

        for ct in chunked_texts:
            orig_text = ct.original_text
            chunk_result_pairs = results_by_orig.get(ct.original_index, [])

            # Collect all predictions with adjusted offsets
            all_predictions: list[NERPrediction] = []
            total_time = 0.0

            for chunk_idx, result in sorted(chunk_result_pairs, key=lambda x: x[0]):
                offset = ct.chunk_offsets[chunk_idx]
                total_time += result.processing_time_ms

                for pred in result.predictions:
                    # Adjust offsets
                    adjusted = NERPrediction(
                        start=pred.start + offset,
                        end=pred.end + offset,
                        text=orig_text[pred.start + offset : pred.end + offset],
                        entity_type=pred.entity_type,
                        score=pred.score,
                        source=pred.source,
                    )
                    all_predictions.append(adjusted)

            # Deduplicate overlapping predictions
            deduped = self._deduplicate_predictions(all_predictions)

            final_results.append(
                NERResult(
                    text=orig_text,
                    predictions=deduped,
                    processing_time_ms=total_time,
                    model_name=self._provider.name,
                )
            )

        return final_results

    def _deduplicate_predictions(
        self,
        predictions: list[NERPrediction],
    ) -> list[NERPrediction]:
        """
        Deduplicate predictions from overlapping chunks.

        Strategy: Keep higher-scoring prediction for overlaps.
        """
        if len(predictions) < 2:
            return predictions

        # Sort by start position
        sorted_preds = sorted(predictions, key=lambda p: (p.start, -p.score))

        deduped: list[NERPrediction] = []
        for pred in sorted_preds:
            # Check for overlap with existing
            is_duplicate = False
            for existing in deduped:
                if self._is_same_entity(pred, existing):
                    # Keep higher scoring one
                    if pred.score > existing.score:
                        deduped.remove(existing)
                        deduped.append(pred)
                    is_duplicate = True
                    break
                elif pred.overlaps_with(existing):
                    # Overlapping but different - keep higher score
                    if pred.score <= existing.score:
                        is_duplicate = True
                        break

            if not is_duplicate:
                deduped.append(pred)

        return sorted(deduped, key=lambda p: p.start)

    def _is_same_entity(
        self,
        pred1: NERPrediction,
        pred2: NERPrediction,
    ) -> bool:
        """Check if two predictions refer to the same entity."""
        # Same type and significant overlap
        if pred1.entity_type != pred2.entity_type:
            return False

        # Calculate overlap
        overlap_start = max(pred1.start, pred2.start)
        overlap_end = min(pred1.end, pred2.end)

        if overlap_start >= overlap_end:
            return False

        overlap_len = overlap_end - overlap_start
        min_len = min(pred1.length, pred2.length)

        # Consider same if >80% overlap
        return overlap_len / min_len > 0.8

    def _calculate_batch_count(self, texts: list[str]) -> int:
        """Calculate expected number of batches."""
        total_chunks = sum(
            max(1, len(t) // self._batch_config.max_text_length + 1)
            for t in texts
        )
        return (total_chunks + self._batch_config.batch_size - 1) // self._batch_config.batch_size


__all__ = [
    "BatchConfig",
    "BatchProgress",
    "NERBatchProcessor",
]
