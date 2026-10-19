# Starter project

Copy this starter, then replace its contents with your own. It validates with no findings, and it shows the keys that pieces keep needing but that sit deep in the schema:

- **`badge`**: an image that pops in on an overshoot bezier (`y` above 1 makes the overshoot), inside a static circular `mask`.
- **`title`**: two runs, where the second changes colour partway through with `highlight`. The title fades in, then cuts out on a `step`. It says `caption: false` because it is a title, not a caption.
- **`bed`**: music at an explicit `volume`.

Its times follow `montagent://format.md` § Time (half-open ranges), and each one lands on a drawn frame at 30 fps.

`fontVendor` comes from running `montagent fonts vendor` on your own font. Leave that entry to the tool, and write only the `fonts` chain yourself.

```json
{
  "frame": {"width": 1920, "height": 1080},
  "fps": 30,
  "background": "#101418",
  "duration": 4000,
  "output": "out/starter.mp4",
  "fonts": {"title": [{"file": "fonts/Inter-Bold.ttf"}]},
  "fontVendor": {"fonts/Inter-Bold.ttf": {"licence": "OFL-1.1", "source": "https://github.com/rsms/inter", "sha256": "288316099b1e0a47a4716d159098005eef7c0066921f34e3200393dbdb01947f"}},
  "tracks": [
    {
      "name": "badge",
      "layer": 10,
      "elements": [
        {"id":"badge","type":"image","start":0,"end":4000,"source":"media/still.png","x":960,"y":420,"origin":"center","width":360,"height":360,"fit":"contain","scale":[{"t":0,"v":[0.0,0.0]},{"t":400,"v":[1.0,1.0],"ease":[0.34,1.56,0.64,1]}],"effects":[{"name":"mask","shape":"circle","x":0,"y":0,"width":360,"height":360}]}
      ]
    },
    {
      "name": "title",
      "layer": 20,
      "elements": [
        {"id":"title","type":"text","start":300,"end":4000,"x":960,"y":760,"origin":"center","width":1400,"height":116,"font":"title","size":96,"color":"#F5F0E6","align":"center","runs":[{"text":"Made with "},{"text":"Montagent","highlight":{"start":1200,"end":4000,"color":"#FF5A36"}}],"opacity":[{"t":300,"v":0.0},{"t":600,"v":1.0,"ease":"ease-out"},{"t":3500,"v":0.0,"ease":"step"}],"caption":false}
      ]
    },
    {
      "name": "music",
      "layer": 0,
      "elements": [
        {"id":"bed","type":"audio","start":0,"end":4000,"source":"media/bed.wav","source_start":0,"source_end":4000,"volume":0.6}
      ]
    }
  ]
}
```
