import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const bindings = JSON.parse(await readFile(new URL('./bindings.json', import.meta.url), 'utf8'));
const routes = Object.keys(bindings.bindings);

assert.equal(routes.length, 4);
assert.ok(routes.includes('say://local/echo/message'));
assert.ok(routes.includes('shell://local/echo/message'));
assert.equal(bindings.bindings['media://local/video/transcode'].inputSchema.properties.width.default, 1280);
assert.equal(bindings.bindings['package://pypi/urirun/install'].argv.at(-1), '{requirement}');

console.log('PASS html_uri_app v8');
