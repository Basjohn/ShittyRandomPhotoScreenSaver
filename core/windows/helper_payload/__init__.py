"""
Placeholder package for shipping the frozen Reddit helper payload.

The build scripts copy ``SRPSS_RedditHelper.exe`` into this directory so it can
be bundled inside the main SCR executable via Nuitka's include-data-files
mechanism.  At runtime the payload is extracted to ``%ProgramData%\\SRPSS\\helper``.
"""
