#!/usr/bin/env python3
from pathlib import Path

p = Path("app/src/main/kotlin/com/bydmate/app/assistantlab/AssistantLab.kt")
s = p.read_text()
old = '''            val info = runCatching { @Suppress("DEPRECATION") pm.getPackageInfo(pkg, PackageManager.GET_ACTIVITIES or PackageManager.GET_SERVICES) }.getOrNull()
'''
new = '''            val info = runCatching { @Suppress("DEPRECATION") pm.getPackageInfo(pkg, PackageManager.GET_ACTIVITIES or PackageManager.GET_SERVICES or PackageManager.GET_PERMISSIONS) }.getOrNull()
'''
if old not in s:
    raise SystemExit("Build91 package-info anchor missing")
s = s.replace(old, new, 1)
old2 = '''            AssistantLabTrace.add("YANDEX-PROFILE pkg=$pkg present=true version=${info.versionName} launcher=${pm.getLaunchIntentForPackage(pkg)?.component ?: "null"}")
'''
new2 = '''            AssistantLabTrace.add("YANDEX-PROFILE pkg=$pkg present=true version=${info.versionName} launcher=${pm.getLaunchIntentForPackage(pkg)?.component ?: "null"}")
            info.requestedPermissions.orEmpty().take(80).forEach { perm ->
                val granted = pm.checkPermission(perm, pkg) == PackageManager.PERMISSION_GRANTED
                AssistantLabTrace.add("YANDEX-PERM pkg=$pkg granted=$granted perm=$perm")
            }
'''
if old2 not in s:
    raise SystemExit("Build91 permissions anchor missing")
s = s.replace(old2, new2, 1)
p.write_text(s)
print("Build91 Yandex permission snapshot applied")
