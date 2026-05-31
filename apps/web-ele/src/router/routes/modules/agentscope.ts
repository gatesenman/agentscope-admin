import type { RouteRecordRaw } from 'vue-router';

import { $t } from '#/locales';

const routes: RouteRecordRaw[] = [
  {
    meta: {
      icon: 'lucide:bot',
      order: -10,
      title: $t('agentscope.title'),
    },
    name: 'AgentScope',
    path: '/agentscope',
    children: [
      {
        name: 'AgentScopeDashboard',
        path: '/agentscope/dashboard',
        component: () => import('#/views/agentscope/dashboard/index.vue'),
        meta: {
          affixTab: true,
          icon: 'lucide:layout-dashboard',
          title: $t('agentscope.menu.dashboard'),
        },
      },
      {
        name: 'AgentScopeAgents',
        path: '/agentscope/agents',
        component: () => import('#/views/agentscope/agents/index.vue'),
        meta: {
          icon: 'lucide:bot',
          title: $t('agentscope.menu.agents'),
        },
      },
      {
        name: 'AgentScopeOntology',
        path: '/agentscope/ontology',
        component: () => import('#/views/agentscope/ontology/index.vue'),
        meta: {
          icon: 'lucide:network',
          title: $t('agentscope.menu.ontology'),
        },
      },
      {
        name: 'AgentScopeCredentials',
        path: '/agentscope/credentials',
        component: () => import('#/views/agentscope/credentials/index.vue'),
        meta: {
          icon: 'lucide:key-round',
          title: $t('agentscope.menu.credentials'),
        },
      },
      {
        name: 'AgentScopeSessions',
        path: '/agentscope/sessions',
        component: () => import('#/views/agentscope/sessions/index.vue'),
        meta: {
          icon: 'lucide:messages-square',
          title: $t('agentscope.menu.sessions'),
        },
      },
      {
        name: 'AgentScopeSchedules',
        path: '/agentscope/schedules',
        component: () => import('#/views/agentscope/schedules/index.vue'),
        meta: {
          icon: 'lucide:calendar-clock',
          title: $t('agentscope.menu.schedules'),
        },
      },
      {
        name: 'AgentScopeWorkflow',
        path: '/agentscope/workflow',
        component: () => import('#/views/agentscope/workflow/index.vue'),
        meta: {
          icon: 'lucide:workflow',
          title: $t('agentscope.menu.workflow'),
        },
      },
      {
        name: 'AgentScopeWorkflowEditor',
        path: '/agentscope/workflow/:id',
        component: () => import('#/views/agentscope/workflow/editor.vue'),
        meta: {
          activePath: '/agentscope/workflow',
          hideInMenu: true,
          title: $t('agentscope.menu.workflow'),
        },
      },
      {
        name: 'AgentScopeKnowledge',
        path: '/agentscope/knowledge',
        component: () => import('#/views/agentscope/knowledge/index.vue'),
        meta: {
          icon: 'lucide:book-open',
          title: $t('agentscope.menu.knowledge'),
        },
      },
      {
        name: 'AgentScopeMcp',
        path: '/agentscope/mcp',
        component: () => import('#/views/agentscope/mcp/index.vue'),
        meta: {
          icon: 'lucide:server',
          title: $t('agentscope.menu.mcp'),
        },
      },
      {
        name: 'AgentScopeObservability',
        path: '/agentscope/observability',
        component: () => import('#/views/agentscope/observability/index.vue'),
        meta: {
          icon: 'lucide:activity',
          title: $t('agentscope.menu.observability'),
        },
      },
      {
        name: 'AgentScopeOrchestration',
        path: '/agentscope/orchestration',
        component: () => import('#/views/agentscope/orchestration/index.vue'),
        meta: {
          icon: 'lucide:git-merge',
          title: $t('agentscope.menu.orchestration'),
        },
      },
      {
        name: 'AgentScopePublish',
        path: '/agentscope/publish',
        component: () => import('#/views/agentscope/publish/index.vue'),
        meta: {
          icon: 'lucide:rocket',
          title: $t('agentscope.menu.publish'),
        },
      },
      {
        name: 'AgentScopeIntegration',
        path: '/agentscope/integration',
        component: () => import('#/views/agentscope/integration/index.vue'),
        meta: {
          icon: 'lucide:plug',
          title: $t('agentscope.menu.integration'),
        },
      },
    ],
  },
];

export default routes;
