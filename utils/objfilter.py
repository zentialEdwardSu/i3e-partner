import copy
import re


def _parse_path(path: str):
    # extract tokens inside [...] and convert numeric tokens to int, ':' stays as ':'
    toks = re.findall(r"\[([^\]]*)\]", path)
    res = []
    for t in toks:
        if t == ":":
            res.append(":")
        else:
            if t.isdigit():
                res.append(int(t))
            else:
                res.append(t)
    return res


def _add_path(mask: dict, tokens: list):
    # set leaf to True to indicate keep/remove whole subtree
    if not tokens:
        return
    key = tokens[0]
    if key not in mask:
        mask[key] = {}
    if len(tokens) == 1:
        mask[key] = True
        return
    if mask[key] is True:
        # already whole subtree
        return
    _add_path(mask[key], tokens[1:])


def _build_mask(paths: list) -> dict:
    mask = {}
    for p in paths or []:
        toks = _parse_path(p)
        if toks:
            _add_path(mask, toks)
    return mask


def _apply_keep(obj, mask):
    # if mask True -> keep whole obj
    if mask is True:
        return copy.deepcopy(obj)
    if isinstance(obj, dict):
        out = {}
        for k, sub in mask.items():
            # only keep keys specified in mask
            if k in obj:
                res = _apply_keep(obj[k], sub)
                out[k] = res
        return out
    if isinstance(obj, list):
        out = []
        # support ':' for all elements
        if ":" in mask:
            sub = mask[":"]
            for item in obj:
                out.append(_apply_keep(item, sub))
            return out
        # or specific indices
        for k, sub in mask.items():
            if isinstance(k, int) and 0 <= k < len(obj):
                out.append(_apply_keep(obj[k], sub))
        return out
    # primitive
    return copy.deepcopy(obj)


def _apply_exclude(obj, mask):
    # if mask True -> remove whole object
    if mask is True:
        return None
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in mask:
                # if submask True -> exclude entire key
                if mask[k] is True:
                    continue
                # else recurse
                res = _apply_exclude(v, mask[k])
                if res is None:
                    continue
                out[k] = res
            else:
                # keep as is
                out[k] = copy.deepcopy(v)
        return out
    if isinstance(obj, list):
        # if mask has ':' handle all elements
        if ":" in mask:
            sub = mask[":"]
            out = []
            for item in obj:
                res = _apply_exclude(item, sub)
                if res is not None:
                    out.append(res)
            return out
        # otherwise mask may contain indices to exclude/sub-filter
        out = []
        for idx, item in enumerate(obj):
            if idx in mask:
                sub = mask[idx]
                if sub is True:
                    # exclude this index
                    continue
                res = _apply_exclude(item, sub)
                if res is not None:
                    out.append(res)
            else:
                out.append(copy.deepcopy(item))
        return out
    # primitive
    return copy.deepcopy(obj)


def filter_structure(obj, spec: dict):
    """
    Filter a Python structure (dict/list/primitive) by spec:
     spec example:
      {"keep": ["[author_id]", "[authors][:][name]"]}
      {"exclude": ["[authors][0]", "[abstract]"]}
     Rules:
      - If 'keep' present: result only contains fields specified by keep paths.
      - Else if 'exclude' present: result contains everything except fields matched by exclude paths.
      - Paths use bracket notation: [key], [index], [:] for all list elements.
    """
    if not isinstance(spec, dict) or not spec:
        return copy.deepcopy(obj)
    if "keep" in spec and spec.get("keep"):
        mask = _build_mask(spec.get("keep"))  # type: ignore
        return _apply_keep(obj, mask)
    if "exclude" in spec and spec.get("exclude"):
        mask = _build_mask(spec.get("exclude"))  # type: ignore
        return _apply_exclude(obj, mask)
    # nothing to do
    return copy.deepcopy(obj)


def build_spec_from_args(args):
    """
    Build a filtering spec from CLI arguments.
    """
    keep = _collect_paths(getattr(args, "keep", None) or []) + _collect_paths(
        getattr(args, "fields", None) or []
    )
    exclude = _collect_paths(getattr(args, "exclude", None) or [])
    spec = {}
    if keep:
        spec["keep"] = keep
    elif exclude:
        spec["exclude"] = exclude
    return spec if spec else None


def _field_to_bracket(path: str) -> str:
    """
    Convert convenient dot/array notation to bracket path.
    Examples:
      "author_id" -> "[author_id]"
      "authors.author_id" -> "[authors][author_id]"
      "authors[].author_id" -> "[authors][:][author_id]"
      "authors[0].name" -> "[authors][0][name]"
      "authors[:].name" -> "[authors][:][name]"
    """
    parts = []
    # split by '.' but keep any existing [...] tokens as part
    tokens = []
    buf = ""
    for ch in path:
        if ch == ".":
            if buf != "":
                tokens.append(buf)
                buf = ""
        else:
            buf += ch
    if buf != "":
        tokens.append(buf)
    for tok in tokens:
        # handle token like name[], name[:], name[0]
        if tok.endswith("[]"):
            name = tok[:-2]
            parts.append(f"[{name}]")
            parts.append("[:]")
        elif tok.endswith("[:]") or tok.endswith("[:"):
            # allow authors[:] or authors[:]
            name = tok.split("[", 1)[0]
            parts.append(f"[{name}]")
            parts.append("[:]")
        elif "[" in tok and "]" in tok:
            # keep as is, but ensure bracket positions are separate tokens
            # e.g. authors[0] -> [authors][0]
            name, rest = tok.split("[", 1)
            index = rest.rstrip("]")
            parts.append(f"[{name}]")
            if index == ":":
                parts.append("[:]")
            elif index.isdigit():
                parts.append(f"[{index}]")
            else:
                parts.append(f"[{index}]")
        else:
            parts.append(f"[{tok}]")
    return "".join(parts)


def _collect_paths(arg_list):
    """
    Normalize input: arg_list can be None, list of strings possibly comma-separated.
    Return flattened list of bracket paths.
    """
    if not arg_list:
        return []
    out = []
    for entry in arg_list:
        if entry is None:
            continue
        # support comma-separated values in one arg
        for part in entry.split(","):
            part = part.strip()
            if not part:
                continue
            # if already looks like bracket path, keep
            if part.startswith("["):
                out.append(part)
            else:
                out.append(_field_to_bracket(part))
    return out
