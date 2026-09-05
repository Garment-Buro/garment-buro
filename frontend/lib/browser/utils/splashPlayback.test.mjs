import assert from 'node:assert/strict';
import test from 'node:test';
import { playSplashVideo } from './splashPlayback.ts';

function fakeVideo(play) {
    const attributes = new Map([['controls', '']]);
    return {
        attributes,
        setAttribute: (key, value) => attributes.set(key, value),
        removeAttribute: (key) => attributes.delete(key),
        play,
    };
}

test('splash configures muted inline video and starts synchronously for user gestures', async () => {
    let called = false;
    const video = fakeVideo(() => {
        called = true;
        assert.equal(video.muted, true);
        assert.equal(video.defaultMuted, true);
        assert.equal(video.playsInline, true);
        assert.equal(video.autoplay, true);
        return Promise.resolve();
    });
    const result = playSplashVideo(video);
    assert.equal(called, true);
    assert.equal(await result, 'playing');
    assert.equal(video.attributes.has('webkit-playsinline'), true);
    assert.equal(video.attributes.has('controls'), false);
});

for (const [name, expected] of [['NotAllowedError', 'blocked'], ['NotSupportedError', 'error'], ['AbortError', 'interrupted']]) {
    test(`splash handles ${name} without swallowing the playback state`, async () => {
        const error = Object.assign(new Error(name), { name });
        assert.equal(await playSplashVideo(fakeVideo(() => Promise.reject(error))), expected);
        assert.equal(await playSplashVideo(fakeVideo(() => { throw error; })), expected);
    });
}

test('splash can recover after autoplay is blocked', async () => {
    let attempts = 0;
    const video = fakeVideo(() => ++attempts === 1
        ? Promise.reject(Object.assign(new Error('blocked'), { name: 'NotAllowedError' }))
        : Promise.resolve());
    assert.equal(await playSplashVideo(video), 'blocked');
    assert.equal(await playSplashVideo(video), 'playing');
});
