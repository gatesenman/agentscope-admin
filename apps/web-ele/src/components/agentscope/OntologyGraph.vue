<script lang="ts" setup>
import type { OntologyGraph } from '#/api/agentscope';

import { computed } from 'vue';

import { ElEmpty } from 'element-plus';

interface Props {
  graph?: OntologyGraph;
}

const props = defineProps<Props>();

const width = 720;
const height = 420;
const radius = 150;

const positioned = computed(() => {
  const nodes = props.graph?.nodes ?? [];
  const cx = width / 2;
  const cy = height / 2;
  const map = new Map<string, { x: number; y: number }>();
  const placed = nodes.map((node, i) => {
    const angle = (2 * Math.PI * i) / Math.max(nodes.length, 1);
    const x = cx + radius * Math.cos(angle);
    const y = cy + radius * Math.sin(angle);
    map.set(node.id, { x, y });
    return { ...node, x, y };
  });
  const edges = (props.graph?.edges ?? []).map((edge) => ({
    ...edge,
    from: map.get(edge.source),
    to: map.get(edge.target),
  }));
  return { nodes: placed, edges };
});
</script>

<template>
  <ElEmpty
    v-if="!graph || graph.nodes.length === 0"
    description="No object types"
  />
  <svg
    v-else
    :height="height"
    :viewBox="`0 0 ${width} ${height}`"
    :width="width"
    class="max-w-full"
  >
    <defs>
      <marker
        id="arrow"
        markerHeight="6"
        markerWidth="8"
        orient="auto"
        refX="8"
        refY="3"
      >
        <path d="M0,0 L8,3 L0,6 Z" fill="#94a3b8" />
      </marker>
    </defs>
    <g>
      <template v-for="edge in positioned.edges" :key="edge.id">
        <line
          v-if="edge.from && edge.to"
          :x1="edge.from.x"
          :x2="edge.to.x"
          :y1="edge.from.y"
          :y2="edge.to.y"
          marker-end="url(#arrow)"
          stroke="#94a3b8"
          stroke-width="1.5"
        />
      </template>
    </g>
    <g v-for="node in positioned.nodes" :key="node.id">
      <circle
        :cx="node.x"
        :cy="node.y"
        :fill="node.color"
        r="26"
        stroke="#fff"
        stroke-width="2"
      />
      <text
        :x="node.x"
        :y="node.y + 44"
        fill="currentColor"
        font-size="12"
        text-anchor="middle"
      >
        {{ node.label }}
      </text>
    </g>
  </svg>
</template>
