"""
macOS Finder integration: installs a Finder Quick Action and a Droplet Application
to allow right-clicking or dropping any .ims, .im7, .vc7 file or folder.
"""
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path


APP_SCRIPT_TEMPLATE = """
on open droppedFiles
    set pyExec to {py_exec_quoted}
    repeat with aFile in droppedFiles
        set posixPath to POSIX path of aFile
        do shell script pyExec & " -m readim7.viewer.standalone " & quoted form of posixPath & " > /dev/null 2>&1 &"
    end repeat
end open

on run
    set pyExec to {py_exec_quoted}
    try
        set chosen to choose file with prompt "Select a DaVis file (.ims, .im7, .vc7):"
        set posixPath to POSIX path of chosen
        do shell script pyExec & " -m readim7.viewer.standalone " & quoted form of posixPath & " > /dev/null 2>&1 &"
    end try
end run
"""

WORKFLOW_INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>NSServices</key>
    <array>
        <dict>
            <key>NSBackgroundColorName</key>
            <string>background</string>
            <key>NSBackgroundStrokeColorName</key>
            <string>line</string>
            <key>NSChannel</key>
            <string>readim7-view</string>
            <key>NSIconName</key>
            <string>NSTouchBarColorPickerFont</string>
            <key>NSMenuItem</key>
            <dict>
                <key>default</key>
                <string>Open with readim7-view</string>
            </dict>
            <key>NSMessage</key>
            <string>runWorkflowAsService</string>
            <key>NSRequiredContext</key>
            <dict>
                <key>NSApplicationIdentifier</key>
                <string>com.apple.finder</string>
            </dict>
            <key>NSSendFileTypes</key>
            <array>
                <string>public.item</string>
            </array>
        </dict>
    </array>
</dict>
</plist>
"""

WORKFLOW_DOCUMENT_WFLOW = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>AMApplicationBuild</key>
    <string>523</string>
    <key>AMApplicationVersion</key>
    <string>2.10</string>
    <key>AMDocumentVersion</key>
    <string>2</string>
    <key>actions</key>
    <array>
        <dict>
            <key>action</key>
            <dict>
                <key>AMAccepts</key>
                <dict>
                    <key>Container</key>
                    <string>List</string>
                    <key>Optional</key>
                    <true/>
                    <key>Types</key>
                    <array>
                        <string>com.apple.cocoa.string</string>
                    </array>
                </dict>
                <key>AMActionVersion</key>
                <string>2.0.3</string>
                <key>AMApplication</key>
                <array>
                    <string>Automator</string>
                </array>
                <key>AMParameterProperties</key>
                <dict>
                    <key>COMMAND_STRING</key>
                    <dict/>
                    <key>CheckedForUserDefaultShell</key>
                    <dict/>
                    <key>inputMethod</key>
                    <dict/>
                    <key>shell</key>
                    <dict/>
                    <key>source</key>
                    <dict/>
                </dict>
                <key>AMProvides</key>
                <dict>
                    <key>Container</key>
                    <string>List</string>
                    <key>Types</key>
                    <array>
                        <string>com.apple.cocoa.string</string>
                    </array>
                </dict>
                <key>ActionBundlePath</key>
                <string>/System/Library/Automator/Run Shell Script.action</string>
                <key>ActionName</key>
                <string>Run Shell Script</string>
                <key>ActionParameters</key>
                <dict>
                    <key>COMMAND_STRING</key>
                    <string>{command_string}</string>
                    <key>CheckedForUserDefaultShell</key>
                    <true/>
                    <key>inputMethod</key>
                    <integer>1</integer>
                    <key>shell</key>
                    <string>/bin/zsh</string>
                    <key>source</key>
                    <string></string>
                </dict>
                <key>BundleIdentifier</key>
                <string>com.apple.RunShellScript</string>
                <key>CFBundleVersion</key>
                <string>2.0.3</string>
                <key>CanShowSelectedItemsWhenRun</key>
                <false/>
                <key>CanShowWhenRun</key>
                <true/>
                <key>Category</key>
                <array>
                    <string>AMCategoryUtilities</string>
                </array>
                <key>Class Name</key>
                <string>RunShellScriptAction</string>
                <key>InputUUID</key>
                <string>C53B2F7E-3844-429E-86EE-6BC69A73C87F</string>
                <key>Keywords</key>
                <array>
                    <string>Shell</string>
                    <string>Script</string>
                    <string>Command</string>
                    <string>Run</string>
                    <string>Unix</string>
                </array>
                <key>OutputUUID</key>
                <string>E9C6C1B1-2856-4279-847B-71F520B8C8A5</string>
                <key>UUID</key>
                <string>FB08DC17-8B41-4C5F-917C-FE2A803A0905</string>
                <key>UnlocalizedApplications</key>
                <array>
                    <string>Automator</string>
                </array>
                <key>arguments</key>
                <dict>
                    <key>0</key>
                    <dict>
                        <key>default value</key>
                        <integer>0</integer>
                        <key>name</key>
                        <string>inputMethod</string>
                        <key>required</key>
                        <string>0</string>
                        <key>type</key>
                        <string>0</string>
                    </dict>
                    <key>1</key>
                    <dict>
                        <key>default value</key>
                        <string></string>
                        <key>name</key>
                        <string>source</string>
                        <key>required</key>
                        <string>0</string>
                        <key>type</key>
                        <string>0</string>
                    </dict>
                    <key>2</key>
                    <dict>
                        <key>default value</key>
                        <false/>
                        <key>name</key>
                        <string>CheckedForUserDefaultShell</string>
                        <key>required</key>
                        <string>0</string>
                        <key>type</key>
                        <string>0</string>
                    </dict>
                    <key>3</key>
                    <dict>
                        <key>default value</key>
                        <string></string>
                        <key>name</key>
                        <string>COMMAND_STRING</string>
                        <key>required</key>
                        <string>0</string>
                        <key>type</key>
                        <string>0</string>
                    </dict>
                    <key>4</key>
                    <dict>
                        <key>default value</key>
                        <string>/bin/sh</string>
                        <key>name</key>
                        <string>shell</string>
                        <key>required</key>
                        <string>0</string>
                        <key>type</key>
                        <string>0</string>
                    </dict>
                </dict>
            </dict>
        </dict>
    </array>
    <key>connectors</key>
    <dict/>
    <key>workflowMetaData</key>
    <dict>
        <key>workflowTypeIdentifier</key>
        <string>com.apple.Automator.servicesMenu</string>
    </dict>
</dict>
</plist>
"""


def get_python_executable():
    """Locate appropriate python interpreter."""
    return sys.executable


def install_macos_droplet(target_dir=None):
    """Compile a macOS application droplet using osacompile."""
    if sys.platform != "darwin":
        print("macOS droplet installation is only supported on macOS.")
        return None

    if target_dir is None:
        target_dir = Path.home() / "Applications"
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    
    app_path = target_dir / "readim7 Viewer.app"
    py_exec = get_python_executable()
    
    script_source = APP_SCRIPT_TEMPLATE.format(
        py_exec_quoted=f'"{py_exec}"'
    )
    
    cmd = ["/usr/bin/osacompile", "-e", script_source, "-o", str(app_path)]
    subprocess.run(cmd, check=True)
    print(f"✓ Installed macOS Droplet App: {app_path}")
    print("  You can now drag & drop files onto this app or use Finder 'Open With'.")
    return app_path


def install_finder_quick_action():
    """Install Finder Quick Action workflow into ~/Library/Services."""
    if sys.platform != "darwin":
        print("Finder Quick Action is only supported on macOS.")
        return None

    services_dir = Path.home() / "Library" / "Services"
    services_dir.mkdir(parents=True, exist_ok=True)

    workflow_path = services_dir / "Open with readim7-view.workflow"
    contents_dir = workflow_path / "Contents"
    contents_dir.mkdir(parents=True, exist_ok=True)

    py_exec = get_python_executable()
    shell_command = f'for f in "$@"; do\n  "{py_exec}" -m readim7.viewer.standalone "$f" >/dev/null 2>&1 &\ndone'
    
    # Escape XML entities
    xml_escaped_command = (
        shell_command.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

    with open(contents_dir / "Info.plist", "w", encoding="utf-8") as f:
        f.write(WORKFLOW_INFO_PLIST)

    with open(contents_dir / "document.wflow", "w", encoding="utf-8") as f:
        f.write(WORKFLOW_DOCUMENT_WFLOW.format(command_string=xml_escaped_command))

    print(f"✓ Installed Finder Quick Action: {workflow_path}")
    print("  You can now right-click any file/folder in Finder -> Quick Actions -> Open with readim7-view.")
    return workflow_path


def main():
    print("Setting up readim7 Finder integration on macOS...")
    install_macos_droplet()
    install_finder_quick_action()
    print("Setup complete!")


if __name__ == "__main__":
    main()
