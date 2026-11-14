import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, utimes, rm, readdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { captureFrame, imageItem } from './vision.mjs';

test('a fresh provided frame becomes a JPEG image input; stale frames are rejected', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'vision-test-'));
  const path = join(directory, 'source.png');
  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64');
  try {
    await writeFile(path, png);
    const bytes = await captureFrame(path);
    assert.equal(bytes.readUInt16BE(0), 0xffd8);
    const event = imageItem(bytes);
    assert.equal(event.type, 'conversation.item.create');
    assert.equal(event.item.role, 'user');
    const input = event.item.content.find(part => part.type === 'input_image');
    assert.ok(input.image_url.startsWith('data:image/jpeg;base64,'));
    assert.deepEqual(Buffer.from(input.image_url.split(',')[1], 'base64'), bytes);
    const old = new Date(Date.now() - 10000);
    await utimes(path, old, old);
    await assert.rejects(captureFrame(path), /stale/);
    assert.deepEqual(await readdir(directory), ['source.png']);
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test('missing capture source fails instead of sending another image', async () => {
  await assert.rejects(captureFrame('/nonexistent/facetime-test.jpg'), /ENOENT/);
});
