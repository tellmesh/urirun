import http from 'node:http';
import { dispatch } from '../../adapters/js/index.js';

const registry = {
  device: {
    led_set(target, state, payload) {
      return { ok: true, payload, state, target };
    },
  },
};

async function readJson(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  return JSON.parse(Buffer.concat(chunks).toString('utf8') || '{}');
}

function writeJson(res, status, value) {
  const raw = JSON.stringify(value, null, 2);
  res.writeHead(status, {
    'Content-Length': Buffer.byteLength(raw),
    'Content-Type': 'application/json; charset=utf-8',
  });
  res.end(raw);
}

const server = http.createServer(async (req, res) => {
  if (req.method !== 'POST' || req.url !== '/dispatch') {
    writeJson(res, 404, { error: 'not found', ok: false });
    return;
  }

  try {
    const body = await readJson(req);
    writeJson(res, 200, await dispatch(body.uri, registry, body.payload));
  } catch (error) {
    writeJson(res, 400, { error: String(error), ok: false });
  }
});

server.listen(3000, '127.0.0.1', () => {
  console.log('urirun node example listening on http://127.0.0.1:3000');
});
