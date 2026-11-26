"""The clip pipeline as 12 steps. Each step is a function that reads and writes files in the stream
folder, reports progress, and skips work whose output already exists (so a job can resume)."""
