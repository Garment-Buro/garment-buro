import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();
const roadmapSource = fs.readFileSync(
    path.join(root, "components", "presentation", "PresentationRoadmap.tsx"),
    "utf8",
);
const roadmapStylesSource = fs.readFileSync(
    path.join(root, "components", "presentation", "PresentationRoadmap.module.css"),
    "utf8",
);

test("presentation roadmap cycles the supplied videos in the sticky media column", () => {
    assert.match(roadmapSource, /src:\s*"\/девушка бежит3\.mp4"[\s\S]*?width:\s*52,[\s\S]*?height:\s*132,[\s\S]*?marginLeft:\s*40,[\s\S]*?marginTop:\s*0/);
    assert.match(roadmapSource, /src:\s*"\/парень бежит\.mp4"[\s\S]*?width:\s*63,[\s\S]*?height:\s*131,[\s\S]*?marginLeft:\s*-13,[\s\S]*?marginTop:\s*66/);
    assert.match(roadmapSource, /src:\s*"\/дед бежит\.mp4"[\s\S]*?width:\s*74,[\s\S]*?height:\s*129,[\s\S]*?marginLeft:\s*40,[\s\S]*?marginTop:\s*130/);
    assert.match(roadmapSource, /const \[activeVideoIndex,\s*setActiveVideoIndex\] = useState\(0\)/);
    assert.match(roadmapSource, /const boyActivationLine = activationLine \+ 100/);
    assert.match(roadmapSource, /const grandpaActivationLine = activationLine \+ 160/);
    assert.match(roadmapSource, /stepRefs\.current\[0\][\s\S]*?boyActivationLine[\s\S]*?nextActiveVideoIndex = 1/);
    assert.match(roadmapSource, /stepRefs\.current\[1\][\s\S]*?grandpaActivationLine[\s\S]*?nextActiveVideoIndex = ROADMAP_VIDEOS\.length - 1/);
    assert.match(roadmapSource, /index <= activeVideoIndex \? styles\.videoActive/);
    assert.match(roadmapSource, /className=\{styles\.videoStage\}[\s\S]*?data-roadmap-video-stage/);
    assert.match(roadmapSource, /autoPlay[\s\S]*?muted[\s\S]*?loop[\s\S]*?playsInline/);
    assert.match(roadmapStylesSource, /\.mediaColumn\s*\{[\s\S]*?position:\s*sticky/);
    assert.match(roadmapStylesSource, /\.mediaCaption\s*\{[\s\S]*?height:\s*75px;[\s\S]*?margin-bottom:\s*30px/);
    assert.match(roadmapStylesSource, /\.videoStage\s*\{[\s\S]*?position:\s*relative;[\s\S]*?height:\s*132px/);
    assert.match(roadmapStylesSource, /\.video\s*\{[\s\S]*?width:\s*var\(--roadmap-video-width\);[\s\S]*?height:\s*var\(--roadmap-video-height\);[\s\S]*?margin-top:\s*var\(--roadmap-video-margin-top\);[\s\S]*?margin-left:\s*var\(--roadmap-video-margin-left\);[\s\S]*?opacity 300ms ease-out,[\s\S]*?visibility 0s linear 300ms/);
    assert.match(roadmapStylesSource, /\.videoActive\s*\{[\s\S]*?opacity:\s*1;[\s\S]*?visibility:\s*visible;[\s\S]*?transition-delay:\s*0s/);
});
