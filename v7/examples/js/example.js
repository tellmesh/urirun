import { compileRegistry, run } from './urirun-v7.js';

const registry = compileRegistry({
  bindings: {
    'media://local/video/transcode': {
      command: ['ffmpeg', '-i', '{input}', '-vf', 'scale={width}:{height}', '{output}'],
      params: { input: { required: true }, output: { required: true }, width: { default: 1280 }, height: { default: 720 } },
    },
    'say://local/echo/msg': 'echo {text}',
  },
});

// Dry-run shows the exact command that named params would produce.
const preview = await run('media://local/video/transcode', registry, { input: 'in.mp4', output: 'out.mp4' });
console.log('ffmpeg:', preview.result.command.join(' '));

// Execute a real command through the policy gate.
const result = await run('say://local/echo/msg', registry, { text: 'hello v7' }, {
  mode: 'execute',
  policy: { execute: { allow: ['say://**'] } },
});
console.log('echo:', result.ok, result.result.stdout.trim());
