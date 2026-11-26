# Feral Streams GTA review

Run the Python GTA review server on port 8766, then use pnpm install and pnpm dev in this frontend. Open http://127.0.0.1:3107. Set GTA_REVIEW_ORIGIN if the Python server listens elsewhere.

The Library and its stylesheet live in app/. Next.js forwards session and media requests to the Python GTA review server.
