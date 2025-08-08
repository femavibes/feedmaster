// Configuration management functions to replace in AdminView.vue

const configFunctions = `
      // Configuration management
      loadGeoConfig: async () => {
        try {
          geoHashtags.value = await apiCall('/config/geo-hashtags')
        } catch (error) {
          alert('Failed to load geo config: ' + error.message)
        }
      },
      
      loadDomainsConfig: async () => {
        try {
          newsDomains.value = await apiCall('/config/news-domains')
        } catch (error) {
          alert('Failed to load domains config: ' + error.message)
        }
      },
      
      addGeoEntry: async () => {
        const hashtag = newGeoEntry.value.hashtag.toLowerCase().replace(/[^a-z0-9]/g, '')
        if (!hashtag) return
        
        try {
          await apiCall('/config/geo-hashtags', {
            method: 'POST',
            body: JSON.stringify({
              hashtag,
              city: newGeoEntry.value.city || null,
              region: newGeoEntry.value.region || null,
              country: newGeoEntry.value.country
            })
          })
          await loadGeoConfig()
          newGeoEntry.value = { hashtag: '', city: '', region: '', country: '' }
        } catch (error) {
          alert('Failed to add geo entry: ' + error.message)
        }
      },
      
      deleteGeoEntry: async (hashtag) => {
        if (!confirm(\`Delete hashtag mapping for "\${hashtag}"?\`)) return
        try {
          await apiCall(\`/config/geo-hashtags/\${hashtag}\`, { method: 'DELETE' })
          await loadGeoConfig()
        } catch (error) {
          alert('Failed to delete geo entry: ' + error.message)
        }
      },
      
      addDomain: async () => {
        const domain = newDomain.value.toLowerCase().replace(/^https?:\\/\\//, '').replace(/\\/$/, '')
        if (!domain || newsDomains.value.includes(domain)) return
        
        try {
          await apiCall('/config/news-domains', {
            method: 'POST',
            body: JSON.stringify({ domain })
          })
          await loadDomainsConfig()
          newDomain.value = ''
        } catch (error) {
          alert('Failed to add domain: ' + error.message)
        }
      },
      
      deleteDomain: async (domain) => {
        if (!confirm(\`Remove "\${domain}" from news domains?\`)) return
        try {
          await apiCall(\`/config/news-domains/\${domain}\`, { method: 'DELETE' })
          await loadDomainsConfig()
        } catch (error) {
          alert('Failed to delete domain: ' + error.message)
        }
      },
`;

console.log(configFunctions);