#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the Kodi add-on repository: the newest zip of every add-on from the GitHub Releases of
the projects, addons.xml with its checksum, and the zip of the repository add-on itself.

    python3 repository/build_repo.py --out site      (GITHUB_TOKEN is used when set)
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OWNER = "ehb"
PROJECTS = {
    "rpi-gpio-spdif": "service.rpi-gpio-spdif",
    "alsa-leadtap": "service.alsa-leadtap",
    "tvlight": "service.tvlight",
}


def fetch(url, api=False):
    headers = {"User-Agent": "pi-lockstep-repository"}
    if api:
        headers["Accept"] = "application/vnd.github+json"
        if os.environ.get("GITHUB_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
        return r.read()


def newest_asset(project, addon):
    """(version, download url) of the highest add-on version over all releases."""
    best = None
    pattern = re.compile(re.escape(addon) + r"-(\d+(?:\.\d+)+)\.zip$")
    releases = json.loads(fetch("https://api.github.com/repos/%s/%s/releases?per_page=100" % (OWNER, project), api=True))
    for release in releases:
        if release["draft"] or release["prerelease"]:
            continue
        for asset in release["assets"]:
            m = pattern.fullmatch(asset["name"])
            if m:
                key = [int(x) for x in m.group(1).split(".")]
                if best is None or key > best[0]:
                    best = (key, m.group(1), asset["browser_download_url"])
    if best is None:
        raise SystemExit("%s: no release with a %s zip" % (project, addon))
    return best[1], best[2]


def addon_element(xml):
    """The <addon> element of an addon.xml, without the XML declaration."""
    return re.sub(r"^\s*<\?xml.*?\?>\s*", "", xml, flags=re.S).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if os.path.exists(a.out):
        shutil.rmtree(a.out)
    os.makedirs(a.out)

    elements = []
    for project, addon in sorted(PROJECTS.items()):
        version, url = newest_asset(project, addon)
        path = os.path.join(a.out, addon, "%s-%s.zip" % (addon, version))
        os.makedirs(os.path.dirname(path))
        with open(path, "wb") as f:
            f.write(fetch(url))
        with zipfile.ZipFile(path) as z:
            elements.append(addon_element(z.read(addon + "/addon.xml").decode("utf-8")))
        print(addon, version)

    source = open(os.path.join(HERE, "addon.xml"), encoding="utf-8").read()
    version = re.search(r'<addon [^>]*\bversion="([^"]+)"', source).group(1)
    zip_name = "repository.ehb-%s.zip" % version
    os.makedirs(os.path.join(a.out, "repository.ehb"))
    with zipfile.ZipFile(os.path.join(a.out, "repository.ehb", zip_name), "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("repository.ehb/addon.xml", source)
    shutil.copy(os.path.join(a.out, "repository.ehb", zip_name), os.path.join(a.out, zip_name))
    elements.append(addon_element(source))

    data = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n%s\n</addons>\n' % "\n".join(elements)).encode("utf-8")
    with open(os.path.join(a.out, "addons.xml"), "wb") as f:
        f.write(data)
    with open(os.path.join(a.out, "addons.xml.md5"), "w", encoding="ascii") as f:
        f.write(hashlib.md5(data).hexdigest())
    with open(os.path.join(a.out, "index.html"), "w", encoding="ascii") as f:
        f.write('<!doctype html><title>pi-lockstep add-ons</title><p>Kodi add-on repository: '
                '<a href="%s">%s</a>. See <a href="https://github.com/ehb/pi-lockstep">pi-lockstep</a>.</p>\n' % (zip_name, zip_name))


if __name__ == "__main__":
    main()
