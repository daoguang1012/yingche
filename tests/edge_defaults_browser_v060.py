"""Actual MV3 storage migration and popup state; no user's Edge profile."""
import json,shutil,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
root=Path(__file__).resolve().parents[1];out=root/'work/v060'/('edge-'+str(time.time_ns()));out.mkdir()
ext=out/'extension';shutil.copytree(root/'edge-extension',ext)
old={'interpolation':True,'swapEnabled':True,'vsrCompatible':False,'beauty':{'smooth':51,'warm':7},'swapTarget':'2'}
with sync_playwright() as p:
    context=p.chromium.launch_persistent_context(str(out/'profile'),executable_path=str(root/'tools/chromium153-test/chrome.exe'),headless=False,args=[f'--disable-extensions-except={ext}',f'--load-extension={ext}'])
    try:
        worker=context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
        ident=worker.url.split('/')[2]
        worker.evaluate('(config)=>chrome.storage.local.set({config})',old)
        page=context.new_page();page.goto(f'chrome-extension://{ident}/popup.html')
        expect(page.locator('#range-smooth')).to_be_attached()
        expect(page.locator('#interpolation')).not_to_be_checked();expect(page.locator('#swapEnabled')).not_to_be_checked()
        expect(page.locator('#vsrCompatible')).not_to_be_checked();expect(page.locator('#number-smooth')).to_have_value('51')
        saved=worker.evaluate('()=>chrome.storage.local.get(null)');assert saved['configBefore060']==old
        page.locator('#interpolation').check();page.wait_for_timeout(250);page.reload();expect(page.locator('#interpolation')).to_be_checked()
        page.locator('#interpolation').uncheck();page.wait_for_timeout(200)
        page.screenshot(path=str(out/'popup.png'),full_page=True)
        result={'passed':True,'version':worker.evaluate('()=>chrome.runtime.getManifest().version'),'migrationBackupPreserved':True,'defaultsOff':True,'manualOptInPersists':True,'vsrChoicePreserved':True}
        assert result['version']=='0.6.0';(out/'edge-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
    finally:context.close()
(root/'work/v060/latest-edge.txt').write_text(str(out),encoding='utf-8')
