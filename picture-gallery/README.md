# Books to Life picture gallery

This folder contains one 720 × 300 PNG per approved scene in the illustrated
catalogue. The files sit together in one flat folder. The gallery prefix in
each filename identifies its story or the shared collection.

[index.json](index.json) is the machine-readable entry point. Each image has
a stable `id`, a `gallery_id`, a description and visual tags. The `file` and
`source_video` paths are relative to this folder. A gallery's `story_id`
matches the Reading Pod's story identifier, with `null` for shared art.

To select a picture, filter `images` by the requested `gallery_id`, then rank
those candidates using their visual descriptions, tags or image content.
Include the `shared` gallery when the selection can use art across stories.
Use the selected image's `file` value to open the PNG.
