# Books

Each book lives in its own folder:

```
books/<book-name>/
├── full_text.txt        the exact text the child reads aloud
└── checkpoints.json     phrases that trigger events (see the main README)
```

The default is Little Mermaid. Open `/?book=tea` for Tea.
Register new book folders in the browser selector and in `guarded_sessions.py`.
