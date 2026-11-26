"""Collect the notices for the libraries shipped inside the frozen PDF helper."""

from importlib.metadata import distribution
from pathlib import Path
import sys
import sysconfig

output = Path(sys.argv[1])
sections = ["ReportPdf bundles CPython, pypdf, and the PyInstaller bootloader."]
python_license = Path(sysconfig.get_path("stdlib")).parent / "LICENSE.txt"
sections.append("CPython\n" + python_license.read_text(encoding="utf-8"))
for name in ("pypdf", "pyinstaller"):
    package = distribution(name)
    notices = [item for item in package.files if item.name.upper() in ("LICENSE", "COPYING", "COPYING.TXT", "LICENSE.TXT")]
    if not notices:
        raise ValueError(f"Could not find the license notice for {name}")
    for notice in notices:
        sections.append(f"{name} {package.version}\n" + notice.locate().read_text(encoding="utf-8"))
output.write_text("\n\n".join(sections), encoding="utf-8")
