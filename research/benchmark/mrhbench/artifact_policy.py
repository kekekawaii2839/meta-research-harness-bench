"""Published per-task collection contract; no hidden global collection budget."""
from .io import ProtocolError

WRITABLE_STORAGE_SEMANTICS = ('per-run total writable tmpfs: /work 80%, /tmp 20%; '
    'charged to container memory; dependency image and read-only inputs excluded. '
    'Collection counts all /work files AND directories except top-level .broker and .process-*; '
    'file-byte total excludes directories and archive metadata. Hard deadline may discard uncaptured tmpfs; '
    'only already captured controller receipts are retained, no periodic backup promised.')


def collection_policy(resources):
    policy = resources.get('artifact_collection')
    if not isinstance(policy, dict):
        raise ProtocolError('Explicit published artifact_collection required; version legacy tasks before new runs')
    expected = {'version', 'max_total_bytes', 'max_entries', 'scope', 'excluded_top_level_rules'}
    if set(policy) != expected or type(policy['version']) is not int or policy['version'] != 1:
        raise ProtocolError('Unsupported artifact collection contract')
    if policy['scope'] != 'all_noninternal_work_files_and_directories' or policy['excluded_top_level_rules'] != ['.broker', '.process-*']:
        raise ProtocolError('Collection scope must match actual controller mechanism')
    total, entries = policy['max_total_bytes'], policy['max_entries']
    if type(total) is not int or not 0 < total <= resources['container']['disk_mb'] * 1024 * 1024:
        raise ProtocolError('Collection bytes must be within published task disk allowance')
    if type(entries) is not int or not 0 < entries <= 100000:
        raise ProtocolError('Collection entries must be explicit, counting files AND directories, at most 100000')
    return dict(policy)


def make_collection_policy(*, max_total_bytes, max_entries):
    return {'version': 1, 'max_total_bytes': max_total_bytes, 'max_entries': max_entries,
            'scope': 'all_noninternal_work_files_and_directories',
            'excluded_top_level_rules': ['.broker', '.process-*']}
