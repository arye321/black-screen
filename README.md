# Black Screen

A small Windows Python app that covers one display or all connected displays with solid black. It does not turn monitors off or change their power settings.

## Run

Install Python 3.10 or later with Tkinter (included in the standard Windows Python installer). No extra packages are required.

Double-click **Start Black Screen.bat**, or run:

```powershell
python black_screen.py
```

1. Select **All screens** or an individual display in the dropdown. Display names match Windows device names; the primary display is labeled.
2. Click **Make black**.
3. Press **Esc** to remove all overlays and return to the app. Mouse clicks and Alt+F4 do not dismiss the black screens.

While black screens are active, a single **Black Screen** entry remains in the Windows taskbar and Alt+Tab switcher, including when covering all displays. Select it to focus the black screen, then press **Esc** to restore.

Use **Refresh screens** after connecting or disconnecting a display. The app also refreshes the display layout before creating overlays. Displays positioned to the left or above the primary display and mixed display scaling are supported.

The black overlays stay above ordinary windows and hide the pointer while it is over them. Windows security screens and other privileged system UI can still appear. A black image does not switch off a monitor's backlight or prevent the usual Windows sleep settings.
