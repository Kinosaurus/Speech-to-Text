# Reading Pod scenes

This is the shared projection media catalogue for the Reading Pod. Put a scene
in its story's subfolder or in [Shared](Shared/) when it is designed for several
stories. A single clip can be assigned to checkpoints in multiple stories.
Open the [scene catalogue](catalogue.html) in a browser to search and play the
illustrated clips.
The [picture gallery](../picture-gallery/README.md) contains the stills and
their machine-readable gallery index.

Use descriptive filenames such as `clouds-over-golden-hills.mp4`. Keep a clip
at its imported path so its MapMap assignments stay valid. Edit cue assignments
to reuse a clip in a new story.

Drop new MP4, MOV, WebM, PNG, and JPEG projection files here. Local sounds and
browser previews with sound are kept with the books.

Use **Preflight → Open MapMap** after following the [Windows setup guide](../docs/READING_POD_SETUP.md). The panel prepares the selected story's scenes in the same MapMap window. The full library and saved wall layout remain in the master project.

Save and close MapMap, then use **Preflight → Import scenes** in the panel. The panel reuses the project's **Wall calibration** meshes, centers and crops media to fill the three walls, and adds each file as a hidden cue. A 2.4:1 asset fills the current wall layout without a crop. Keep imported files here so MapMap can find them.

Use **Edit MapMap cues** above a book's checkpoints to assign an imported scene. Open the updated project in MapMap and use **Reset to grid** before testing projection.

To adjust the layout in the panel, open **Preflight → Output layout → Edit wall layout**. Drag inside a wall shape to select and move the whole wall. Drag its corner handles to reshape it. Use **Ctrl+Z** to undo and **Ctrl+Y** or **Ctrl+Shift+Z** to redo. Each full drag is one undo step. Undo and Redo buttons are also available, and history lasts for the current editor session. With the same project open in MapMap, a temporary preview updates automatically after a 250 ms pause in dragging or nudging corners. **Preview on projector** resends the current draft when needed. Click **Save and apply to all scenes** to write the layout to the master and apply it to the open MapMap window. The selected-story project is saved too, and the current scene stays loaded. Older builds need one restart through **Open MapMap** to install the live-layout update. Scenes with a compatible three-wall mesh keep their source crop and use the new output corners.
