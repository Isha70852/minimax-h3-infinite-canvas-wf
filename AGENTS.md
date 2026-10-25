# Development workspace

This directory is the canonical H3 Canvas development workspace. Do not modify the former sibling 無限畫布 checkout unless explicitly requested.

Use backend/ and src/ for the canvas; workflows/ and workflow_template.json contain sanitized runtime graphs with IDs matched by registries. example_workflows/ contains user-facing ComfyUI exports; its IDs can differ. Keep personal prompts, input filenames, workflow IDs, media, credentials, SQLite databases, caches, dependencies and notebook outputs out of Git and release archives.

colab/ and skills/minimax-h3-remote-skill are independent Colab tools, not the canvas backend. Preserve them independently. Use skills/h3-canvas-api for authorized canvas operations.

Build with npm run build. Run focused checks only; never spend provider credits without user authorization. Package releases with package-share.ps1.
