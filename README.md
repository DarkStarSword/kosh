Kosh Password Manager
=====================

WHY YOU SHOULD NOT USE THIS PASSWORD MANAGER
--------------------------------------------
- The database won't be saved if it hits a bug, which could cause data loss
  (however I've fixed all the bugs I know of that could cause this, and it does
  save pretty aggressively, so as long as you hit save you should be golden)

- It has not been security audited, so keep your password database secure! (If
  you are a security person, feel free to look at the code and tell me how
  stupid I am so we can improve this).

- It currently lacks an ability to change the master password

- On Windows it does not prevent someone attaching a debugger to it and
  extracting the passwords from memory (it does disable ptrace on Linux)

I'm releasing this anyway because I'm working on other projects and just
haven't got around to addressing these issues. Despite these, it is a useful
password manager, just beware the warnings!

Why you might want to use this password manager anyway
------------------------------------------------------
- Runs in a terminal with curses

- Written in Python

- Cross platform. Runs on Linux, Windows, WSL1/2, cygwin, Mac, and even Android
  under Termux, and probably anywhere else you can run Python.

- Keeps a history of the password entries so you can look back in time to see
  what passwords you used to use with Ctrl+p, Ctrl+n.

- Smart multi-platform Clipboard integration. Copies the username field, then
  (on supported platforms) as soon as that has been pasted it will
  AUTOMATICALLY copy the password field, then once that is pasted it will
  automatically clear the clipboard!  Just yank, paste, paste :)

- Database format is designed specifically to make it easy to edit on multiple
  devices and synchronise the changes with external tools (personally I have my
  database in git). Each entry is one line, just concatenate the unique lines
  of two diverged databases together and it will be merged. Even copes with the
  same entry being edited - whichever has the newest timestamp will be the
  current entry, and the other will be in the history.

- All fields are considered equally secure and the contents is hidden until
  explicitly revealed.

- No limitations on what fields can be added to a password entry.

- Ability to log into an SSH server and update the password (this is not fully
  implemented in the UI yet, but the functionality is there by using a
  specially named HACK\_SSH\_name field with the contents set to username@host)

- Ability to record the actions necessary to change a password on an arbitrary
  web service and play it back next time you update your password. (Note: This
  is a bit of a hack at the moment and is not fully integrated into the UI. Use
  the 'Record HTTP password change script' to record a new script, then play it
  back by highlighting it and pressing S. The old password needs to be in
  another field called 'OldPassword' - another hack, once this feature is
  complete it will automatically get the old password from the history)

- Two Factor Authentication (Time-based one-time password) support that will
  automatically handle any fields following the otpauth:// URI format
  (typically imported via QR codes intended for Authenticator apps), allowing
  the 2FA codes to be copied to the clipboard or displayed like other
  authenticator apps.

- QR Code import/export, particularly useful for importing 2FA QR codes from
  the clipboard. (Note that this does not yet support importing from other
  Authenticator apps, only the initial 2FA provisioning QR Codes are supported)

Keys
----
- /: Search for entry

- n: New entry

- e: Edit highlighted entry

- :q : quit

- Enter: Reveal passwords. If used on the left pane it will reveal all fields
  for the highlighted entry, if used in the right pane it will reveal only the
  highlighted field.

- Ctrl+R: Reveal the contents of a field currently being edited.

- y: Copy entry to clipboard. If used in the left pane it will first copy the
  username field, then the password field. If used in the right pane it will
  copy the highlighted field.

- Shift+Y: Copy entry to clipboard in dumb mode. For when you need to paste the
  entry several times, or when dealing with an application / Operating system
  that just doesn't handle the smart clipboard support well.

- g: Open web browser to the URL field of the currently highlighted entry.

- Ctrl+g: Call out to pwgen to generate a random password in the field
  currently being edited.

- Ctrl+p: Show previous entry in history (use from left pane)

- Ctrl+n: Show next entry in history (use from left pane)

- S: Run highlighted SSH / HTTP password change script (note - this is a
  temporary hack until this feature is properly integrated into the UI)

- q: Display selected entry as a QR Code (typically for exporting 2FA entries
  to authenticator apps)

- :set pause : Freeze the count down timer for cases where you need the
  password manager to remain open and unlocked for an extended time. Not
  recommended, use at your own risk and make sure you manually close it when
  you are done.
