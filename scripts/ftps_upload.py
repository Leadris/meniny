"""FTPS upload of a built site folder (called by scripts/deploy.ps1).

WebHouse requires the data connection to reuse the TLS session of the control connection,
so FTP_TLS is subclassed below. The password comes only from the DEPLOY_FTP_PASSWORD
environment variable. Nothing on the server is ever deleted.

  python -I scripts/ftps_upload.py HOST USER ROOT --list
  python -I scripts/ftps_upload.py HOST USER ROOT LOCAL_DIR [--dry-run]
"""
import ftplib
import os
import ssl
import sys


class ReusedSessionFTP(ftplib.FTP_TLS):
    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            conn = self.context.wrap_socket(conn, server_hostname=self.host, session=self.sock.session)
        return conn, size


def connect(host, user, password):
    ftp = ReusedSessionFTP(host, timeout=60, context=ssl.create_default_context())
    ftp.login(user, password)
    ftp.prot_p()
    return ftp


def ensure_dir(ftp, path, known):
    parts = [p for p in path.split("/") if p]
    current = ""
    for part in parts:
        current += "/" + part
        if current in known:
            continue
        try:
            ftp.mkd(current)
        except ftplib.error_perm:
            pass  # exists
        known.add(current)


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        return 2
    host, user = sys.argv[1], sys.argv[2]
    root = "/" + sys.argv[3].strip("/")
    password = os.environ.get("DEPLOY_FTP_PASSWORD")
    if not password:
        print("DEPLOY_FTP_PASSWORD is not set.", file=sys.stderr)
        return 3
    ftp = connect(host, user, password)
    try:
        if sys.argv[4] == "--list":
            target = root if root != "/" else "/"
            print("Remote listing of %s:" % target)
            for name in sorted(ftp.nlst(target)):
                print("  " + name)
            return 0
        local = os.path.abspath(sys.argv[4])
        dry = "--dry-run" in sys.argv[5:]
        # The subdomain folder must already exist (WebHouse creates it with the subdomain).
        # Uploading into a folder nobody serves would look like success, so stop instead.
        try:
            ftp.cwd(root)
        except ftplib.error_perm:
            # WebHouse serves <name>.<domain> from _sub_<domain>/<name> as soon as the folder
            # exists; until then the wildcard shows the main site. Create only that one level.
            parent = root.rsplit("/", 1)[0] or "/"
            if parent.rsplit("/", 1)[-1].startswith("_sub_"):
                try:
                    ftp.cwd(parent)
                    if dry:
                        print("would create " + root)
                    else:
                        ftp.mkd(root)
                        print("created " + root)
                except ftplib.error_perm:
                    pass
        try:
            if not dry:
                ftp.cwd(root)
            else:
                ftp.cwd(root.rsplit("/", 1)[0] or "/")
        except ftplib.error_perm:
            print("Target folder %s does not exist. FTP home contains:" % root, file=sys.stderr)
            for name in sorted(ftp.nlst("/")):
                print("  " + name, file=sys.stderr)
            parent = root.rsplit("/", 1)[0] or "/"
            if parent != "/":
                try:
                    print("%s contains:" % parent, file=sys.stderr)
                    for name in sorted(ftp.nlst(parent)):
                        print("  " + name, file=sys.stderr)
                except ftplib.error_perm:
                    pass
            print("Run again with -Root /<folder of the subdomain>.", file=sys.stderr)
            return 4
        known = set()
        count = 0
        for folder, _dirs, files in os.walk(local):
            for name in sorted(files):
                path = os.path.join(folder, name)
                rel = os.path.relpath(path, local).replace(os.sep, "/")
                remote = root.rstrip("/") + "/" + rel
                count += 1
                if dry:
                    print("would upload " + remote)
                    continue
                ensure_dir(ftp, remote.rsplit("/", 1)[0], known)
                with open(path, "rb") as handle:
                    ftp.storbinary("STOR " + remote, handle)
                print("uploaded " + remote)
        print("%s %d file(s) to %s" % ("would upload" if dry else "uploaded", count, root))
        return 0
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()


if __name__ == "__main__":
    sys.exit(main())
