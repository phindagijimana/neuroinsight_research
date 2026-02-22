# Upload API Files

## Active Implementation

**`upload_simple.py`** - Currently active upload endpoint
- Route: `POST /api/upload/`
- Status: ✅ Production
- Features:
  - Basic file validation (.nii, .nii.gz)
  - Patient data handling
  - Job queue management (max 1 running + 5 pending)
  - Celery task submission with proper routing
  - MinIO/S3 storage integration

## Backup/Reference

**`upload.py.backup`** - Previous implementation (not active)
- Status: ⚠️ Reference only - NOT imported
- Why kept: Contains additional validation features that may be useful:
  - API key authentication
  - Advanced file corruption detection
  - Multi-library validation (nibabel + SimpleITK)
  - Stricter T1 filename validation
  - More comprehensive error handling

## Making Changes

When modifying the upload endpoint:
1. ✅ Edit `upload_simple.py` (active)
2. ❌ Do NOT edit `upload.py.backup` (inactive)
3. Test changes at `POST /api/upload/`

## Switching Implementations

To switch to the more comprehensive upload.py implementation:
1. Rename `upload.py.backup` back to `upload.py`
2. Update `backend/api/__init__.py`:
   ```python
   from .upload import router as upload_router  # instead of upload_simple
   ```
3. Update route path if needed (upload.py uses `/` instead of `/upload/`)
4. Ensure all dependencies are installed (SimpleITK, etc.)
5. Test thoroughly before deploying

## Current Status

- ✅ `upload_simple.py` - Active and working
- 📦 `upload.py.backup` - Archived for reference
- ✅ No route conflicts
- ✅ Clear which file is production
