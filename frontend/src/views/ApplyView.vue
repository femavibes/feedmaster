<template>
  <div class="apply-container">
    <div class="apply-header">
      <h1>🚀 Apply to Join Feedmaster</h1>
      <p>Submit your feed for inclusion in the Feedmaster platform</p>
    </div>

    <div class="apply-content">
      <div v-if="!submitted" class="application-form-section">
        <div class="info-section">
          <h2>📋 Application Requirements</h2>
          <div class="requirements-list">
            <div class="requirement">
              <span class="icon">✅</span>
              <div>
                <strong>Valid Bluesky DID</strong>
                <p>Your decentralized identifier from Bluesky</p>
              </div>
            </div>
            <div class="requirement">
              <span class="icon">👤</span>
              <div>
                <strong>Bluesky Handle</strong>
                <p>Your @username on Bluesky for easy identification</p>
              </div>
            </div>
            <div class="requirement">
              <span class="icon">🆔</span>
              <div>
                <strong>Graze Feed ID</strong>
                <p>Your unique feed ID from Graze Contrails</p>
              </div>
            </div>
            <div class="requirement">
              <span class="icon">📝</span>
              <div>
                <strong>Feed Description</strong>
                <p>Brief description of your feed's purpose and content</p>
              </div>
            </div>
          </div>
        </div>

        <div class="form-section">
          <h2>📝 Submit Your Application</h2>
          <form @submit.prevent="submitApplication" class="application-form">
            <div class="form-group">
              <label for="applicant_did">Your Bluesky DID *</label>
              <input 
                id="applicant_did"
                v-model="application.applicant_did" 
                placeholder="did:plc:..."
                required
              >
              <small>Find your DID in your Bluesky profile settings</small>
            </div>

            <div class="form-group">
              <label for="applicant_handle">Your Bluesky Handle *</label>
              <input 
                id="applicant_handle"
                v-model="application.applicant_handle" 
                placeholder="username.bsky.social"
                required
              >
              <small>Your @username on Bluesky (without the @)</small>
            </div>

            <div class="form-group">
              <label for="feed_id">Graze Feed ID *</label>
              <input 
                id="feed_id"
                v-model="application.feed_id" 
                placeholder="1234"
                required
              >
              <small>Your unique feed ID from Graze Contrails (usually 4 digits)</small>
            </div>

            <div class="form-group">
              <label for="description">Feed Description *</label>
              <textarea 
                id="description"
                v-model="application.description" 
                rows="4"
                placeholder="Describe your feed's purpose, target audience, and content type..."
                required
              ></textarea>
              <small>Help us understand what makes your feed unique</small>
            </div>

            <div class="form-group">
              <label for="applicant_name">Your Name (optional)</label>
              <input 
                id="applicant_name"
                v-model="application.applicant_name" 
                placeholder="John Doe"
              >
              <small>For easier communication during review</small>
            </div>

            <div class="form-group">
              <label for="applicant_email">Contact Email (optional)</label>
              <input 
                id="applicant_email"
                v-model="application.applicant_email" 
                type="email"
                placeholder="john@example.com"
              >
              <small>We'll notify you about your application status</small>
            </div>

            <div class="form-actions">
              <button type="submit" :disabled="loading" class="submit-btn">
                {{ loading ? 'Submitting...' : 'Submit Application' }}
              </button>
            </div>
          </form>
        </div>
      </div>

      <div v-else class="success-section">
        <div class="success-card">
          <div class="success-icon">🎉</div>
          <h2>Application Submitted!</h2>
          <p>Thank you for your interest in joining Feedmaster.</p>
          
          <div class="application-details">
            <div class="detail">
              <strong>Application ID:</strong> {{ applicationId }}
            </div>
            <div class="detail">
              <strong>Feed ID:</strong> {{ application.feed_id }}
            </div>
            <div class="detail">
              <strong>Status:</strong> <span class="status-pending">Pending Review</span>
            </div>
          </div>

          <div class="next-steps">
            <h3>What happens next?</h3>
            <ol>
              <li>Our team will review your application</li>
              <li>We may reach out if we need additional information</li>
              <li>You'll be notified of the decision via your provided contact method</li>
              <li>If approved, you'll receive API credentials to access your dashboard</li>
            </ol>
          </div>

          <div class="status-check">
            <p>You can check your application status anytime:</p>
            <div class="status-url">
              <code>{{ statusUrl }}</code>
              <button @click="copyStatusUrl" class="copy-btn">Copy</button>
            </div>
          </div>

          <button @click="submitAnother" class="secondary-btn">Submit Another Application</button>
        </div>
      </div>

      <!-- Status Checker -->
      <div class="status-checker-section">
        <h2>🔍 Check Application Status</h2>
        <div class="status-form">
          <div class="form-group">
            <label>Application ID:</label>
            <div class="input-group">
              <input 
                v-model="statusCheck.applicationId" 
                placeholder="Enter your application ID"
                type="number"
              >
              <button @click="checkStatus" :disabled="!statusCheck.applicationId" class="check-btn">
                Check Status
              </button>
            </div>
          </div>
          
          <div v-if="statusResult" class="status-result">
            <div class="status-card">
              <h4>Application #{{ statusResult.application_id }}</h4>
              <div class="status-info">
                <div class="info-row">
                  <span>Feed ID:</span>
                  <span>{{ statusResult.feed_id }}</span>
                </div>
                <div class="info-row">
                  <span>Status:</span>
                  <span :class="`status-${statusResult.status}`">{{ statusResult.status }}</span>
                </div>
                <div class="info-row">
                  <span>Applied:</span>
                  <span>{{ new Date(statusResult.applied_at).toLocaleDateString() }}</span>
                </div>
                <div v-if="statusResult.reviewed_at" class="info-row">
                  <span>Reviewed:</span>
                  <span>{{ new Date(statusResult.reviewed_at).toLocaleDateString() }}</span>
                </div>
              </div>
              <div v-if="statusResult.notes" class="status-notes">
                <strong>Notes:</strong>
                <p>{{ statusResult.notes }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed } from 'vue'

export default {
  name: 'ApplyView',
  setup() {
    const loading = ref(false)
    const submitted = ref(false)
    const applicationId = ref(null)
    const statusResult = ref(null)
    
    const application = ref({
      applicant_did: '',
      applicant_handle: '',
      feed_id: '',
      description: '',
      applicant_name: '',
      applicant_email: ''
    })
    
    const statusCheck = ref({
      applicationId: ''
    })

    const submitApplication = async () => {
      loading.value = true
      try {
        const response = await fetch('/api/v1/public/apply', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(application.value)
        })
        
        if (!response.ok) {
          const error = await response.json()
          throw new Error(error.detail || 'Application failed')
        }
        
        const result = await response.json()
        applicationId.value = result.application_id
        submitted.value = true
      } catch (error) {
        alert('Application failed: ' + error.message)
      } finally {
        loading.value = false
      }
    }

    const checkStatus = async () => {
      try {
        const response = await fetch(`/api/v1/public/application-status/${statusCheck.value.applicationId}`)
        
        if (!response.ok) {
          throw new Error('Application not found')
        }
        
        statusResult.value = await response.json()
      } catch (error) {
        alert('Failed to check status: ' + error.message)
        statusResult.value = null
      }
    }

    const copyStatusUrl = () => {
      const url = `${window.location.origin}/apply#status-${applicationId.value}`
      navigator.clipboard.writeText(url)
      alert('Status URL copied to clipboard!')
    }

    const submitAnother = () => {
      submitted.value = false
      applicationId.value = null
      application.value = {
        applicant_did: '',
        applicant_handle: '',
        feed_id: '',
        description: '',
        applicant_name: '',
        applicant_email: ''
      }
    }

    const statusUrl = computed(() => 
      `${window.location.origin}/apply#status-${applicationId.value}`
    )

    return {
      loading,
      submitted,
      applicationId,
      application,
      statusCheck,
      statusResult,
      statusUrl,
      submitApplication,
      checkStatus,
      copyStatusUrl,
      submitAnother
    }
  }
}
</script>

<style scoped>
.apply-container {
  width: 100%;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #333;
}

.apply-header {
  background: rgba(255, 255, 255, 0.95);
  padding: 60px 40px;
  text-align: center;
  box-shadow: 0 2px 20px rgba(0,0,0,0.1);
}

.apply-header h1 {
  font-size: 3em;
  margin: 0 0 20px 0;
  color: #2c3e50;
}

.apply-header p {
  font-size: 1.2em;
  color: #666;
  max-width: 600px;
  margin: 0 auto;
}

.apply-content {
  padding: 60px 40px;
  max-width: 1200px;
  margin: 0 auto;
}

.application-form-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 60px;
  margin-bottom: 60px;
}

.info-section, .form-section {
  background: white;
  border-radius: 12px;
  padding: 40px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.1);
}

.requirements-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.requirement {
  display: flex;
  align-items: flex-start;
  gap: 15px;
}

.requirement .icon {
  font-size: 1.5em;
  margin-top: 5px;
}

.requirement strong {
  color: #2c3e50;
  display: block;
  margin-bottom: 5px;
}

.requirement p {
  color: #666;
  margin: 0;
  font-size: 0.9em;
}

.application-form {
  display: flex;
  flex-direction: column;
  gap: 25px;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.form-group label {
  font-weight: 600;
  margin-bottom: 8px;
  color: #2c3e50;
}

.form-group input, .form-group textarea {
  padding: 12px 16px;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 0.3s;
}

.form-group input:focus, .form-group textarea:focus {
  outline: none;
  border-color: #667eea;
}

.form-group small {
  color: #666;
  font-size: 0.85em;
  margin-top: 5px;
}

.submit-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  padding: 16px 32px;
  border-radius: 8px;
  font-size: 18px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s;
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-2px);
}

.submit-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.success-section {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 60vh;
}

.success-card {
  background: white;
  border-radius: 12px;
  padding: 60px;
  text-align: center;
  box-shadow: 0 10px 30px rgba(0,0,0,0.1);
  max-width: 600px;
}

.success-icon {
  font-size: 4em;
  margin-bottom: 20px;
}

.success-card h2 {
  color: #27ae60;
  margin-bottom: 20px;
}

.application-details {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  margin: 30px 0;
  text-align: left;
}

.detail {
  margin-bottom: 10px;
}

.status-pending {
  color: #f39c12;
  font-weight: 600;
}

.next-steps {
  text-align: left;
  margin: 30px 0;
}

.next-steps ol {
  padding-left: 20px;
}

.next-steps li {
  margin-bottom: 8px;
  color: #666;
}

.status-url {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #f8f9fa;
  padding: 15px;
  border-radius: 8px;
  margin: 10px 0;
}

.status-url code {
  flex: 1;
  font-size: 0.9em;
  word-break: break-all;
}

.copy-btn, .check-btn {
  background: #3498db;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.secondary-btn {
  background: #95a5a6;
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 8px;
  cursor: pointer;
  margin-top: 20px;
}

.status-checker-section {
  background: white;
  border-radius: 12px;
  padding: 40px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.1);
}

.input-group {
  display: flex;
  gap: 10px;
}

.input-group input {
  flex: 1;
}

.status-result {
  margin-top: 20px;
}

.status-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
}

.status-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 15px 0;
}

.info-row {
  display: flex;
  justify-content: space-between;
}

.status-pending { color: #f39c12; }
.status-approved { color: #27ae60; }
.status-rejected { color: #e74c3c; }

.status-notes {
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #ddd;
}

@media (max-width: 768px) {
  .application-form-section {
    grid-template-columns: 1fr;
    gap: 30px;
  }
  
  .apply-header {
    padding: 40px 20px;
  }
  
  .apply-content {
    padding: 40px 20px;
  }
  
  .info-section, .form-section, .status-checker-section {
    padding: 30px 20px;
  }
}
</style>