from pathlib import Path

p = Path('index.html')
s = p.read_text(encoding='utf-8')
marker = '<script src="/vod-ui.js"></script>'
mobile_nav_fix = '<style id="mobile-vod-tabs-fix">@media (max-width: 700px){.vod-tabs{display:none!important}}</style>'

changed = False

if marker not in s:
    if '</body>' not in s:
        raise SystemExit('index.html has no </body> marker')
    s = s.replace('</body>', marker + '</body>', 1)
    changed = True
    print('Injected VOD UI into index.html')

if mobile_nav_fix not in s:
    if '</head>' not in s:
        raise SystemExit('index.html has no </head> marker')
    s = s.replace('</head>', mobile_nav_fix + '</head>', 1)
    changed = True
    print('Injected mobile VOD navigation fix into index.html')

if changed:
    p.write_text(s, encoding='utf-8')
else:
    print('VOD UI and mobile navigation fix already integrated')
