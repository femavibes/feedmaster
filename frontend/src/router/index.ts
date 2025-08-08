import { createRouter, createWebHistory } from 'vue-router'
import FeedView from '../views/FeedView.vue'
import LeaderboardView from '../views/LeaderboardView.vue'

const router = createRouter({
  history: createWebHistory('/'), // Serve the app at the root path
  routes: [
    {
      path: '/',
      name: 'home',
      redirect: to => {
        // This will be handled by the navigation guard below
        return '/feed/3654' // Default to first feed as fallback
      }
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
    },
    {
      path: '/dashboard',
      name: 'feedmaker',
      component: () => import('../views/FeedmakerView.vue')
    },
    {
      path: '/apply',
      name: 'apply',
      component: () => import('../views/ApplyView.vue')
    },
    {
      path: '/geo-hashtags',
      name: 'geo-hashtags',
      component: () => import('../views/GeoHashtagsView.vue')
    }
  ]
})

// Navigation guard to redirect home to first available feed
router.beforeEach(async (to, from, next) => {
  if (to.path === '/') {
    // Try to get feeds from API
    try {
      const response = await fetch('/api/v1/feeds/')
      if (response.ok) {
        const data = await response.json()
        if (data.feeds && data.feeds.length > 0) {
          next(`/feed/${data.feeds[0].id}`)
          return
        }
      }
    } catch (error) {
      console.error('Error fetching feeds for redirect:', error)
    }
    // Fallback to default feed
    next('/feed/3654')
  } else {
    next()
  }
})

export default router