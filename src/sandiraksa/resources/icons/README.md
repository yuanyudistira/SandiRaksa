# Icon Resources

Place application icons here:

- `app.ico` - Windows icon (256x256, 128x128, 64x64, 48x48, 32x32, 16x16)
- `app.icns` - macOS icon
- `app.png` - Linux icon (512x512 recommended)

## Creating Icons

You can create these from a single high-resolution PNG (1024x1024) using tools like:

### Windows (.ico)
```bash
# Using ImageMagick
convert app.png -define icon:auto-resize=256,128,64,48,32,16 app.ico
```

### macOS (.icns)
```bash
# Using iconutil on macOS
mkdir app.iconset
sips -z 16 16     app.png --out app.iconset/icon_16x16.png
sips -z 32 32     app.png --out app.iconset/icon_16x16@2x.png
sips -z 32 32     app.png --out app.iconset/icon_32x32.png
sips -z 64 64     app.png --out app.iconset/icon_32x32@2x.png
sips -z 128 128   app.png --out app.iconset/icon_128x128.png
sips -z 256 256   app.png --out app.iconset/icon_128x128@2x.png
sips -z 256 256   app.png --out app.iconset/icon_256x256.png
sips -z 512 512   app.png --out app.iconset/icon_256x256@2x.png
sips -z 512 512   app.png --out app.iconset/icon_512x512.png
sips -z 1024 1024 app.png --out app.iconset/icon_512x512@2x.png
iconutil -c icns app.iconset
```

### Linux (.png)
Use a high-resolution PNG (512x512 or 1024x1024).
