from sources.models import SourceFile, ProcessingStatus


def set_source_file_status(source_file: SourceFile, status: ProcessingStatus, failed_reason: str = None):
    source_file.status = status
    if failed_reason:
        source_file.failed_reason = failed_reason
    source_file.save()
    source_file.refresh_from_db()
    return source_file