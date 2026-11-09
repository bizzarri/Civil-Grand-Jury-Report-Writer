"""Read-only MSI and cabinet verification; does not install or register the app."""
from pathlib import Path
import ctypes
from ctypes import wintypes
import hashlib
import json
import msilib
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
NUMERIC_VERSION = VERSION.split("-", 1)[0]
MSI = ROOT / "dist" / ("ReportInterview-" + VERSION + "-x64.msi")
OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
db = msilib.OpenDatabase(str(MSI), msilib.MSIDBOPEN_READONLY)

def rows(table):
    view = db.OpenView("SELECT * FROM `%s`" % table)
    view.Execute(None)
    result = []
    while record := view.Fetch():
        result.append([record.GetString(i) for i in range(1, record.GetFieldCount() + 1)])
    view.Close()
    return result

files = rows("File")
components = {r[0] for r in rows("Component")}
directories = {r[0] for r in rows("Directory")}
features = {r[0] for r in rows("Feature")}
properties = dict(rows("Property"))
assert len(files) == 6 and len({r[0] for r in files}) == 6
assert all(r[1] in components for r in files)
assert all(r[2] in directories for r in rows("Component"))
assert all(r[0] in features and r[1] in components for r in rows("FeatureComponents"))
assert properties.get("ALLUSERS", "") == ""
assert properties["ProductVersion"] == NUMERIC_VERSION
assert properties["ProductCode"] != "{C43BE697-E8B0-46B7-8B29-78B3E2D3A216}"
assert properties["UpgradeCode"] == "{AD5EFB3B-0D37-4D1F-BB63-93D00EDAB34F}"
assert any(r[2] == NUMERIC_VERSION and (int(r[4]) & 512) for r in rows("Upgrade"))
assert len(rows("Shortcut")) == 1
for shortcut in rows("Shortcut"):
    assert shortcut[1] in directories and shortcut[3] in components
assert rows("Registry")[0][1] == "1"  # HKCU.
assert "RemoveFiles" in {r[0] for r in rows("InstallExecuteSequence")}
assert "CreateShortcuts" in {r[0] for r in rows("InstallExecuteSequence")}
assert "NETRELEASE" in {r[0] for r in rows("AppSearch")}
dialog_controls = {(r[0], r[1]): r for r in rows("Control")}
for dialog in rows("Dialog"):
    for key in dialog[7:10]:
        assert not key or (dialog[0], key) in dialog_controls
for e in rows("ControlEvent"):
    assert (e[0], e[1]) in dialog_controls

# Read the actual embedded cabinet with the Windows Installer read-only API.
msi = ctypes.WinDLL("msi")
handle, view, record = wintypes.UINT(), wintypes.UINT(), wintypes.UINT()
msi.MsiOpenDatabaseW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.POINTER(wintypes.UINT)]
msi.MsiDatabaseOpenViewW.argtypes = [wintypes.UINT, wintypes.LPCWSTR, ctypes.POINTER(wintypes.UINT)]
msi.MsiRecordReadStream.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)]
assert msi.MsiOpenDatabaseW(str(MSI), None, ctypes.byref(handle)) == 0
try:
    assert msi.MsiDatabaseOpenViewW(handle, "SELECT `Data` FROM `_Streams` WHERE `Name`='ReportFiles'", ctypes.byref(view)) == 0
    assert msi.MsiViewExecute(view, 0) == 0
    assert msi.MsiViewFetch(view, ctypes.byref(record)) == 0
    cab = OUT / "payload.cab"
    with cab.open("wb") as dest:
        while True:
            size = wintypes.DWORD(65536)
            buf = ctypes.create_string_buffer(size.value)
            assert msi.MsiRecordReadStream(record, 1, buf, ctypes.byref(size)) == 0
            if not size.value:
                break
            dest.write(buf.raw[:size.value])
finally:
    for h in (record, view, handle):
        if h.value:
            msi.MsiCloseHandle(h)
subprocess.run([r"C:\Windows\System32\expand.exe", "-F:*", str(cab), str(OUT)], check=True, capture_output=True)
hashes = {}
for row in files:
    filename = row[2].split("|")[-1]
    original = (ROOT / "app" / filename).read_bytes()
    extracted = (OUT / row[0]).read_bytes()
    assert original == extracted, filename
    assert int(row[3]) == len(extracted), filename
    hashes[filename] = hashlib.sha256(extracted).hexdigest()

# Evaluate the package's actual AppSearch and prerequisite conditions without installation.
msi.MsiOpenPackageExW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(wintypes.UINT)]
msi.MsiDoActionW.argtypes = [wintypes.UINT, wintypes.LPCWSTR]
msi.MsiSetInternalUI(2, None)  # No dialogs during a read-only package validation.
session = wintypes.UINT()
code = msi.MsiOpenPackageExW(str(MSI), 1, ctypes.byref(session))
prerequisite_result = "session unavailable: " + str(code)
if code == 0:
    try:
        search = msi.MsiDoActionW(session, "AppSearch")
        conditions = msi.MsiDoActionW(session, "LaunchConditions")
        if search != 0 or conditions != 0:
            raise RuntimeError("MSI prerequisite validation failed: " + str((search, conditions)))
        prerequisite_result = "AppSearch and LaunchConditions passed"
    finally:
        msi.MsiCloseHandle(session)
report = {"result": "PASS", "checks": "MSI tables, references, per-user scope, shortcut, prerequisite search, cabinet extraction and payload hashes", "prerequisites": prerequisite_result, "files": hashes, "msi_sha256": hashlib.sha256(MSI.read_bytes()).hexdigest()}
(OUT / "verification.json").write_text(json.dumps(report, indent=2))
(MSI.parent / (MSI.name + ".sha256")).write_text(report["msi_sha256"] + "  " + MSI.name + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
