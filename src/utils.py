import os, os.path, glob

sbin_paths = ['/sbin', '/usr/sbin'] + os.getenv('PATH', os.defpath).split(os.pathsep)

def sbin_which(name: str) -> str | None:
    for path in sbin_paths:
        maybe_result = os.path.join(path, name)
        if not os.path.isfile(maybe_result) or not os.access(maybe_result, os.X_OK):
            continue
        return maybe_result
    return None

def get_prefixed_dir(exec_name: str, rel: str) -> str | None:
    for prefix in [ os.path.join(os.path.dirname(exec_name), '..'), '/' ]:
        maybe_result = os.path.normpath(os.path.join(prefix, rel))
        if not os.path.isdir(maybe_result):
            continue
        return maybe_result
    return None

# def sbin_which_glob(name_glob: str) -> list[str] | None:
#     results = []
#     for path in sbin_paths:
#         for maybe_result in glob.iglob(os.path.join(path, name_glob)):
#             if not os.path.isfile(result) or not os.access(result, os.X_OK):
#                 continue
#             results.append(maybe_result)
#     return results or None
