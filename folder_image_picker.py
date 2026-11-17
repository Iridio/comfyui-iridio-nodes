import os
import shutil
import subprocess
import sys
import threading

from .folder_image_files import resolve_folder, remember_picked_folder

_dialog_lock = threading.Lock()


def native_folder_dialog(start):
    """Runs on the server desktop, never in the browser's filesystem."""
    if sys.platform == 'darwin' and shutil.which('osascript'):
        script = '''on run argv
            activate
            set location to item 1 of argv
            if location is "" then
                set chosen to choose folder with prompt "Choose an image folder"
            else
                set chosen to choose folder with prompt "Choose an image folder" default location POSIX file location
            end if
            return POSIX path of chosen
        end run'''
        command = ['osascript', '-e', script, '--', start]
        cancel_codes = ()
        options = {}
    elif sys.platform == 'win32' and shutil.which('powershell'):
        script = (
            'Add-Type -AssemblyName System.Windows.Forms;'
            '$picker=New-Object System.Windows.Forms.FolderBrowserDialog;'
            '$picker.Description="Choose an image folder";$picker.ShowNewFolderButton=$false;'
            '$picker.SelectedPath=$env:IRIDIO_START_FOLDER;'
            'if($picker.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK)'
            '{[Console]::Out.Write($picker.SelectedPath)}'
        )
        command = ['powershell', '-NoProfile', '-STA', '-Command', script]
        options = {'env': {**os.environ, 'IRIDIO_START_FOLDER': start}, 'creationflags': 0x08000000}
        cancel_codes = ()
    elif sys.platform.startswith('linux') and (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        if shutil.which('zenity'):
            command = ['zenity', '--file-selection', '--directory', '--title=Choose an image folder']
            if start:
                command.append('--filename=' + start.rstrip('/') + '/')
        elif shutil.which('kdialog'):
            command = ['kdialog', '--getexistingdirectory', start or os.path.expanduser('~'), '--title', 'Choose an image folder']
        else:
            return {'unavailable': True}
        options = {}
        cancel_codes = (1,)
    else:
        return {'unavailable': True}
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300, **options)
    except (OSError, subprocess.TimeoutExpired):
        return {'unavailable': True}
    if result.returncode in cancel_codes or (sys.platform == 'darwin' and '(-128)' in result.stderr):
        return {'cancelled': True}
    if result.returncode:
        return {'unavailable': True}
    path = result.stdout.rstrip('\r\n')
    return {'path': path} if path else {'cancelled': True}


def pick_folder(start=''):
    if not _dialog_lock.acquire(blocking=False):
        return {'busy': True}
    try:
        try:
            start = str(resolve_folder(start)) if start else ''
        except (OSError, ValueError):
            start = ''
        result = native_folder_dialog(start)
        if 'path' in result:
            # Only the OS dialog's result can grant a new root; request paths never do.
            return {'path': remember_picked_folder(result['path'])}
        return result
    finally:
        _dialog_lock.release()
