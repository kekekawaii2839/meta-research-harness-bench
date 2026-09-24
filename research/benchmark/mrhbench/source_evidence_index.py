"""Lossless-text-oriented HTML evidence navigation for material maintainers.

This derived aid is NOT an independent source and never enters solver releases.
MathML's original alttext is preserved instead of flattening duplicated glyphs
and TeX annotations. Complete equation groups prevent continuation-row omission.
"""
from html.parser import HTMLParser


class EvidenceHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.active = []
        self.units = []
        self.math_depth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = a.get("class", "").split()
        if self.math_depth:
            self.math_depth += 1
            return
        if tag == "math" and a.get("alttext"):
            for row in self.active:
                row["parts"].append(" $" + a["alttext"] + "$ ")
            self.math_depth = 1
            return
        if tag in {"br", "hr", "img", "meta", "link", "input", "wbr"}:
            for row in self.active:
                row["parts"].append(" ")
            return
        self.stack.append(tag)
        if a.get("id"):
            for row in self.active:
                row["child_ids"].append(a["id"])
        selected = a.get("id") and (set(classes) & {"ltx_para", "ltx_equationgroup", "ltx_table", "ltx_theorem", "ltx_bibitem"})
        if selected:
            self.active.append({"id": a["id"], "tag": tag, "classes": classes,
                                "depth": len(self.stack), "parts": [], "child_ids": []})

    def handle_endtag(self, tag):
        if self.math_depth:
            self.math_depth -= 1
            return
        depth = len(self.stack)
        for row in list(self.active):
            if row["depth"] == depth:
                self.units.append({k: v for k, v in row.items() if k not in {"depth", "parts"}} |
                                  {"text": " ".join("".join(row["parts"]).split())})
                self.active.remove(row)
        if self.stack:
            self.stack.pop()
        for row in self.active:
            row["parts"].append(" ")

    def handle_data(self, data):
        if not self.math_depth:
            for row in self.active:
                row["parts"].append(data)


def build_evidence_index(html: str, source_id: str, source_sha256: str):
    parser = EvidenceHTMLParser()
    parser.feed(html)
    parser.close()
    return {"schema_version": "source-navigation-1", "source_id": source_id,
            "source_sha256": source_sha256, "derived_not_independent_evidence": True,
            "scope": "Complete selected HTML paragraphs/equation groups/tables/theorems; raw original remains authoritative",
            "units": parser.units}
