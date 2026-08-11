from pathlib import Path

p = Path('index.html')
s = p.read_text(encoding='utf-8')
marker = '<script src="/vod-ui.js"></script>'
if marker not in s:
    if '</body>' not in s:
        raise SystemExit('index.html has no </body> marker')
    s = s.replace('</body>', marker + '</body>', 1)
    p.write_text(s, encoding='utf-8')
    print('Injected VOD UI into index.html')
else:
    print('VOD UI already injected')
