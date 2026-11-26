"""The 12 pipeline steps, one module each.

Every step reads its inputs from the stream folder, writes its output there (most under <stream>/auto/),
reports progress through ctx.report(), and returns a short summary. When its output already exists,
the step reports 100% and returns at once, so a job resumes where it stopped.
"""
