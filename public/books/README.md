# Books

Each book lives in its own folder:

```
books/<book-name>/
├── full_text.txt        the exact text the child reads aloud
└── checkpoints.json     phrases that trigger events (see the main README)
```

To switch book, change `BOOK_NAME` at the top of `public/src/app.js`.
