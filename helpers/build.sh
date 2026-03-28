#!/usr/bin/env bash
#
# Uses https://github.com/apple/container and pandoc to output the HTML docs

container system start;

container run --rm \
    -v "$(pwd):/data" \
    -w /data \
    --arch amd64 \
    pandoc/extra \
    README.md \
    -o readme.html \
    --embed-resources \
    --standalone \
    --from markdown-tex_math_dollars \
    --css resources/css/sakura.css \
    --metadata pagetitle="Raspberry Pi Write Blocker: Setup"

container run --rm \
    -v "$(pwd):/data" \
    -w /data \
    --arch amd64 \
    pandoc/extra \
    docs/archive/setup-steps.md \
    -o docs/archive/setup-steps.html \
    --embed-resources \
    --standalone \
    --from markdown-tex_math_dollars \
    --css resources/css/sakura.css \
    --metadata pagetitle="Raspberry Pi Write Blocker: Methodology"

container image prune --all;
container image rm --all;
container system stop
