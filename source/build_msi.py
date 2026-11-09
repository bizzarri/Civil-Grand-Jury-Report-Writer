"""Build the native MSI with Python 3.11's Windows Installer bindings.

Python is a build dependency only; no Python is installed on the target machine.
"""
from pathlib import Path
import msilib
from msilib import schema, sequence
import hashlib
import uuid
import ctypes

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
DIST = ROOT / "dist"
DIST.mkdir(parents=True, exist_ok=True)
MSI = DIST / "ReportInterview-2.0.0-x64.msi"
PRODUCT = "{C43BE697-E8B0-46B7-8B29-78B3E2D3A216}"
UPGRADE = "{AD5EFB3B-0D37-4D1F-BB63-93D00EDAB34F}"
COMPONENT = "{C1C03184-7A50-40D4-8214-0F2715968DAD}"

def add(table, rows):
    msilib.add_data(db, table, rows)

db = msilib.init_database(str(MSI), schema, "Report Interview", PRODUCT, "2.0.0", "Report Interview")
si = db.GetSummaryInformation(3)
si.SetProperty(msilib.PID_TEMPLATE, "x64;1033")
si.SetProperty(msilib.PID_WORDCOUNT, 10)  # Compressed, per-user, no elevation required.
si.SetProperty(msilib.PID_PAGECOUNT, 200)
si.Persist()
add("Property", [
    ("UpgradeCode", UPGRADE), ("INSTALLLEVEL", "1"), ("DefaultUIFont", "Normal"),
    ("ARPCOMMENTS", "Guided local report authoring. No browser, AI or cloud processing."),
    ("ARPNOMODIFY", "1"), ("ARPINSTALLLOCATION", "[INSTALLDIR]"),
    ("SecureCustomProperties", "OLDERPRODUCTS;NEWERPRODUCTS;NETRELEASE;WINDOWSBUILD"),
])
add("Directory", [
    ("TARGETDIR", None, "SourceDir"),
    ("LocalAppDataFolder", "TARGETDIR", "."),
    ("ProgramsDir", "LocalAppDataFolder", "Programs"),
    ("INSTALLDIR", "ProgramsDir", "REPORT~1|ReportInterview"),
    ("ProgramMenuFolder", "TARGETDIR", "."),
    ("MenuDir", "ProgramMenuFolder", "REPORT~1|Report Interview"),
])
add("Feature", [("Main", None, "Report Interview", "Native guided report authoring", 1, 1, "INSTALLDIR", 0)])
# HKCU key path permits proper per-user repair and avoids machine-wide registry writes.
add("Component", [("App", COMPONENT, "INSTALLDIR", 260, None, "InstallMarker")])
add("FeatureComponents", [("Main", "App")])
add("Registry", [("InstallMarker", 1, r"Software\ReportInterview\Desktop", "Version", "2.0.0", "App")])
add("CreateFolder", [("INSTALLDIR", "App"), ("MenuDir", "App")])
add("RemoveFile", [("RemoveMenuDir", "App", None, "MenuDir", 2)])
cab = msilib.CAB("ReportFiles")
names = ["ReportInterview.exe", "ReportEngine.exe", "ReportInterview.exe.config", "Read me.txt", "LICENSE.txt", "NOTICE.txt"]
for index, name in enumerate(names, 1):
    full = APP / name
    key = "File" + str(index)
    seq, _ = cab.append(str(full), name, key)
    short = {1: "REPORT~1.EXE", 2: "ENGINE.EXE", 3: "REPORT~1.CON", 4: "README.TXT", 5: "LICENSE.TXT", 6: "NOTICE.TXT"}[index]
    version = "2.0.0.0" if index == 1 else None
    add("File", [(key, "App", short + "|" + name, full.stat().st_size, version, "1033" if version else None, 512, seq)])
    if not version:
        class FileHash(ctypes.Structure):
            _fields_ = [("size", ctypes.c_uint32), ("parts", ctypes.c_uint32 * 4)]
        h = FileHash()
        h.size = ctypes.sizeof(h)
        get_hash = ctypes.windll.msi.MsiGetFileHashW
        get_hash.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.POINTER(FileHash)]
        code = get_hash(str(full), 0, ctypes.byref(h))
        if code:
            raise OSError(code, "MsiGetFileHashW failed")
        add("MsiFileHash", [(key, 0, *[ctypes.c_int32(n).value for n in h.parts])])
add("Shortcut", [("StartMenu", "MenuDir", "REPORT~1|Report Interview", "App", "[#File1]", None,
                    "Write and resume reports using the revised accessible template", None, None, None, 1, "INSTALLDIR")])
add("Upgrade", [(UPGRADE, None, "2.0.0", None, 1, None, "OLDERPRODUCTS"),
                (UPGRADE, "2.0.0", None, None, 2, None, "NEWERPRODUCTS")])
add("AppSearch", [("NETRELEASE", "NetFrameworkRelease"), ("WINDOWSBUILD", "WindowsBuild")])
add("RegLocator", [("NetFrameworkRelease", 2, r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full", "Release", 18),
                   ("WindowsBuild", 2, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "CurrentBuildNumber", 18)])
add("LaunchCondition", [
    ("Installed OR (VersionNT64 AND (WINDOWSBUILD >= 10240))", "Report Interview requires 64-bit Windows 10 or Windows 11."),
    ('Installed OR (NETRELEASE AND (NETRELEASE >= "#528040"))', "Microsoft .NET Framework 4.8 or later is required. Enable or update it through Windows before installing."),
    ("NOT NEWERPRODUCTS", "A newer Report Interview version is already installed."),
    ("NOT ALLUSERS", "This installer installs for the current Windows user only. Do not set ALLUSERS."),
])
# Reuse the Windows Installer standard file, shortcut, registry, repair and removal actions.
execute = list(sequence.InstallExecuteSequence)
execute = [(a, c, 500 if a == "LaunchConditions" else n) for a, c, n in execute]
add("InstallExecuteSequence", execute)
add("AdminExecuteSequence", sequence.AdminExecuteSequence)
add("InstallUISequence", [("FindRelatedProducts", None, 200), ("AppSearch", None, 400),
    ("LaunchConditions", None, 500), ("CostInitialize", None, 800), ("FileCost", None, 900),
    ("CostFinalize", None, 1000), ("WelcomeDlg", "NOT Installed", 1100),
    ("MaintenanceDlg", "Installed AND NOT REMOVE", 1150), ("ExecuteAction", None, 1300),
    ("ExitDlg", None, -1), ("ErrorDlg", None, -3), ("CancelDlg", None, -2)])
add("TextStyle", [("Normal", "Segoe UI", 10, 0, 0), ("Heading", "Segoe UI", 16, 0, 1)])

def text(dlg, key, x, y, w, h, text):
    add("Control", [(dlg, key, "Text", x, y, w, h, 3, None, text, None, None)])

def button(dlg, key, x, text, next_key=None):
    add("Control", [(dlg, key, "PushButton", x, 212, 85, 22, 3, None, text, next_key, None)])

def event(dlg, control, event, arg, order=1):
    add("ControlEvent", [(dlg, control, event, arg, "1", order)])

def dialog(name, title, first, default, cancel):
    add("Dialog", [(name, 50, 50, 380, 250, 3, title, first, default, cancel)])

dialog("WelcomeDlg", "Install Report Interview", "Install", "Install", "Cancel")
text("WelcomeDlg", "Title", 20, 18, 340, 35, "{\\Heading}Report Interview")
text("WelcomeDlg", "Body", 20, 65, 340, 128,
     "Install the native Windows report authoring application for your account.\r\n\r\n"
     "No browser, web server, Python installation, AI or cloud connection is required.\r\n\r\n"
     "Your existing drafts are not modified. After installation, use File > Import existing draft to bring in a browser-version draft.")
button("WelcomeDlg", "Install", 180, "&Install", "Cancel")
button("WelcomeDlg", "Cancel", 275, "Cancel", "Install")
event("WelcomeDlg", "Install", "EndDialog", "Return")
event("WelcomeDlg", "Cancel", "EndDialog", "Exit")
dialog("MaintenanceDlg", "Maintain Report Interview", "Repair", "Repair", "Cancel")
text("MaintenanceDlg", "Title", 20, 18, 340, 35, "{\\Heading}Report Interview")
text("MaintenanceDlg", "Body", 20, 65, 340, 115,
     "Choose Repair to restore the installed application files, or Remove to uninstall.\r\n\r\nSaved reports and drafts are kept in your user profile and will not be removed.")
button("MaintenanceDlg", "Repair", 85, "&Repair", "Remove")
button("MaintenanceDlg", "Remove", 180, "&Remove", "Cancel")
button("MaintenanceDlg", "Cancel", 275, "Cancel", "Repair")
event("MaintenanceDlg", "Repair", "[REINSTALL]", "ALL")
event("MaintenanceDlg", "Repair", "[REINSTALLMODE]", "omus", 2)
event("MaintenanceDlg", "Repair", "EndDialog", "Return", 3)
event("MaintenanceDlg", "Remove", "[REMOVE]", "ALL")
event("MaintenanceDlg", "Remove", "EndDialog", "Return", 2)
event("MaintenanceDlg", "Cancel", "EndDialog", "Exit")
for name, title, body in [
    ("ExitDlg", "Report Interview setup complete", "Setup completed successfully.\r\n\r\nAfter installation or repair, open Report Interview from the Windows Start menu.\r\n\r\nYour saved drafts are retained when the application is removed."),
    ("ErrorDlg", "Setup did not complete", "Setup could not complete. No report drafts have been removed.\r\n\r\nIf your organization restricts software installation, contact your administrator."),
    ("CancelDlg", "Setup canceled", "Setup was canceled. Your saved report drafts have not been removed."),
]:
    dialog(name, title, "Finish", "Finish", "Finish")
    text(name, "Title", 20, 18, 340, 35, "{\\Heading}" + title)
    text(name, "Body", 20, 65, 340, 130, body)
    button(name, "Finish", 275, "Finish", "Finish")
    event(name, "Finish", "EndDialog", "Return")
cab.commit(db)
db.Commit()
print(MSI)
digest = hashlib.sha256(MSI.read_bytes()).hexdigest()
(DIST / (MSI.name + ".sha256")).write_text(digest + "  " + MSI.name + "\n", encoding="utf-8")
print("SHA256", digest)
