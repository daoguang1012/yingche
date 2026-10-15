"""An old MV3 service worker must request reload before using new popup files."""
import json, shutil, time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/v050';EXT=OUT/'upgrade-test-extension'
shutil.copytree(OUT/'edge-extension',EXT,dirs_exist_ok=True)
shutil.copy2(OUT/'backup-v042/background.js',EXT/'background.js')
with sync_playwright() as p:
 context=p.chromium.launch_persistent_context(str(OUT/('upgrade-profile-'+str(time.time_ns()))),executable_path=str(ROOT/'tools/chromium153-test/chrome.exe'),headless=False,args=[f'--disable-extensions-except={EXT}',f'--load-extension={EXT}'])
 worker=context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
 extension_id=worker.url.split('/')[2]
 settings=context.new_page();settings.goto('chrome://extensions/');settings.locator('#devMode').click();settings.close()
 page=context.new_page();page.goto(f'chrome-extension://{extension_id}/popup.html')
 expect(page.locator('#reloadExtension')).to_be_visible();expect(page.locator('#enable')).to_be_disabled()
 expect(page.locator('#message')).to_contain_text('后台仍是旧版')
 shutil.copy2(OUT/'edge-extension/background.js',EXT/'background.js')
 page.locator('#reloadExtension').click();time.sleep(.5)
 page=context.new_page()
 for attempt in range(6):
  try:page.goto(f'chrome-extension://{extension_id}/popup.html');break
  except Exception:
   if attempt==5:
    page=context.new_page();page.goto('chrome://extensions/');page.wait_for_timeout(500);print(page.locator('body').inner_text(),flush=True)
    print(page.locator('extensions-item').evaluate_all('(items)=>items.map(x=>({id:x.data?.id,state:x.data?.state,disableReasons:x.data?.disableReasons,installWarnings:x.data?.installWarnings,errors:x.data?.runtimeErrors}))'),flush=True)
    raise
   time.sleep(1)
 expect(page.locator('#range-smooth')).to_be_attached();expect(page.locator('#enable')).to_be_enabled();expect(page.locator('#reloadExtension')).to_be_hidden()
 expect(page.locator('#interpolation')).to_be_checked()
 version=page.evaluate('chrome.runtime.sendMessage({type:"config"}).then(r=>r.extensionVersion)');assert version=='0.5.0'
 result={'passed':True,'oldBackgroundBlocked':True,'reloadButtonWorks':True,'version':version}
 (OUT/'upgrade-acceptance.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
 context.close()
