import { createRouter, createWebHistory } from 'vue-router'
import FeedView from '../views/FeedView.vue'
import LeaderboardView from '../views/LeaderboardView.vue'

const router = createRouter({
  history: createWebHistory('/'), // Serve the app at the root path
  routes: [
    {
      path: '/',
      name: 'home',
      component: FeedView
    },
    {
      path: '/feed/:feed_id',
      name: 'feed',
      component: FeedView,
      props: true // Allows feed_id to be passed as a prop to FeedView
    },
    {
      path: '/leaderboard',
      name: 'leaderboard',
      component: LeaderboardView
    },
    {
      path: '/admin',
      name: 'admin',
      // This is lazy-loaded, meaning it's only fetched when the user navigates to it.
      component: () => import('../views/AdminView.vue')
    }
  ]
})

export default router