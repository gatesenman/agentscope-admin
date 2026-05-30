<script lang="ts" setup>
import { computed } from 'vue';

import { ElTag } from 'element-plus';

interface Props {
  status?: string;
}

const props = defineProps<Props>();

const type = computed<'danger' | 'info' | 'primary' | 'success' | 'warning'>(
  () => {
    switch ((props.status || '').toLowerCase()) {
      case 'active':
      case 'enabled':
      case 'online':
      case 'published':
      case 'running': {
        return 'success';
      }
      case 'archived':
      case 'disabled':
      case 'offline': {
        return 'info';
      }
      case 'draft': {
        return 'warning';
      }
      case 'error':
      case 'failed': {
        return 'danger';
      }
      default: {
        return 'primary';
      }
    }
  },
);
</script>

<template>
  <ElTag :type="type" effect="light">{{ status || 'unknown' }}</ElTag>
</template>
