// Production JavaScript with error boundaries and performance optimizations

class ReverseImageSearch {
    constructor() {
        this.API_BASE = window.location.origin;
        this.currentSessionId = null;
        this.searchInProgress = false;
        
        this.initializeEventListeners();
        this.showEmptyState();
        this.focusFirstInput();
        
        // Production: Preload critical resources
        this.preloadImages();
    }
    
    initializeEventListeners() {
        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.switchTab(e.target.dataset.tab || e.target.closest('.tab-btn').dataset.tab));
        });
        
        // Form submissions
        document.querySelectorAll('.search-form').forEach(form => {
            form.addEventListener('submit', (e) => e.preventDefault());
        });
        
        // File handling
        this.initializeFileUpload();
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));
        
        // Network status
        window.addEventListener('online', () => this.showStatus('✅ Back online', 'success'));
        window.addEventListener('offline', () => this.showStatus('⚠️ Connection lost', 'warning'));
    }
    
    async switchTab(tab) {
        // Update UI
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
            btn.setAttribute('aria-selected', 'false');
        });
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        
        const activeBtn = document.querySelector(`[onclick="switchTab('${tab}')"]`) || 
                         document.querySelector(`[data-tab="${tab}"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
            activeBtn.setAttribute('aria-selected', 'true');
        }
        
        document.getElementById(`${tab}Tab`).classList.add('active');
        
        // Focus management
        const focusable = document.querySelector(`#${tab}Tab [autofocus], #${tab}Tab input`);
        if (focusable) {
            focusable.focus();
        }
        
        // Reset state
        this.resetSearchState();
        this.showEmptyState();
    }
    
    initializeFileUpload() {
        const fileInput = document.getElementById('fileUpload');
        const dropzone = document.getElementById('fileDropzone');
        const preview = document.getElementById('filePreview');
        const fileName = document.getElementById('fileName');
        const searchBtn = document.getElementById('fileSearchBtn');
        
        // Click handler
        dropzone.addEventListener('click', () => fileInput.click());
        
        // File selection
        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                this.handleFileSelect(file, preview, fileName, searchBtn);
            } else {
                this.resetFileInput(preview, fileName, searchBtn);
            }
        });
        
        // Drag and drop
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, this.preventDefaults, false);
        });
        
        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, () => dropzone.classList.add('dragover'), false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, () => dropzone.classList.remove('dragover'), false);
        });
        
        dropzone.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files.length > 0 && files[0].type.startsWith('image/')) {
                fileInput.files = files;
                fileInput.dispatchEvent(new Event('change', { bubbles: true }));
            } else {
                this.showStatus('❌ Please drop an image file only', 'error');
            }
        });
    }
    
    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    async handleFileSelect(file, preview, fileName, searchBtn) {
        // Production: File validation
        if (!file.type.startsWith('image/')) {
            this.showStatus('❌ Please select an image file', 'error');
            return;
        }
        
        if (file.size > 8 * 1024 * 1024) { // 8MB
            this.showStatus('❌ File too large (max 8MB)', 'error');
            return;
        }
        
        // Show preview
        const reader = new FileReader();
        reader.onload = (e) => {
            preview.querySelector('img').src = e.target.result;
            preview.style.display = 'block';
        };
        reader.readAsDataURL(file);
        
        fileName.textContent = file.name;
        preview.parentElement.parentElement.classList.add('has-file');
        searchBtn.disabled = false;
        searchBtn.querySelector('.btn-text').textContent = '🔍 Search';
        
        this.showStatus(`✅ Selected: ${this.formatFileSize(file.size)}`, 'success');
    }
    
    resetFileInput(preview, fileName, searchBtn) {
        document.getElementById('fileUpload').value = '';
        preview.style.display = 'none';
        fileName.textContent = '';
        preview.parentElement.parentElement.classList.remove('has-file');
        searchBtn.disabled = true;
        searchBtn.querySelector('.btn-text').textContent = 'Select File First';
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    async searchByUrl(event) {
        event.preventDefault();
        const url = document.getElementById('urlInput').value.trim();
        const maxResults = Math.min(parseInt(document.getElementById('maxResults').value), 50);
        
        if (!url || !this.isValidUrl(url)) {
            this.showStatus('❌ Please enter a valid image URL (http:// or https://)', 'error');
            document.getElementById('urlInput').focus();
            return;
        }
        
        if (this.searchInProgress) return;
        
        this.startSearch('URL', maxResults, async () => {
            await this.executeFullSearch(url, 'url', maxResults);
        });
    }
    
    async searchByFile(event) {
        event.preventDefault();
        const fileInput = document.getElementById('fileUpload');
        const file = fileInput.files[0];
        const maxResults = Math.min(parseInt(document.getElementById('fileMaxResults').value), 50);
        
        if (!file) {
            this.showStatus('❌ Please select a file first', 'error');
            return;
        }
        
        if (this.searchInProgress) return;
        
        this.startSearch('File', maxResults, async () => {
            await this.executeFileSearch(file, maxResults);
        });
    }
    
    async startSearch(type, maxResults, searchFunction) {
        this.searchInProgress = true;
        this.currentSessionId = null;
        
        const progress = document.getElementById('progress');
        const progressFill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');
        
        progress.style.display = 'block';
        this.updateProgress(0, 'Initializing secure search session...');
        
        try {
            await searchFunction();
        } catch (error) {
            console.error('Search error:', error);
            this.showStatus(`❌ Search failed: ${error.message}`, 'error');
        } finally {
            this.searchInProgress = false;
            progress.style.display = 'none';
            progressFill.style.width = '0%';
        }
    }
    
    async executeFullSearch(url, type, maxResults) {
        this.updateProgress(10, '🔐 Starting secure session...');
        
        // Step 1: Initialize session
        const startResponse = await fetch(`${this.API_BASE}/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (!startResponse.ok) {
            throw new Error(`Session init failed: ${startResponse.status}`);
        }
        
        const startData = await startResponse.json();
        if (startData.status !== 'success') {
            throw new Error(startData.error || 'Session initialization failed');
        }
        
        this.currentSessionId = startData.session_id;
        this.showSessionInfo(startData);
        this.updateProgress(30, '📤 Performing secure image search...');
        
        // Step 2: Search
        const searchResponse = await fetch(`${this.API_BASE}/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: this.currentSessionId,
                type: type,
                value: url
            })
        });
        
        if (!searchResponse.ok) {
            throw new Error(`Search failed: ${searchResponse.status}`);
        }
        
        const searchData = await searchResponse.json();
        if (searchData.status !== 'success') {
            throw new Error(searchData.error || 'Search execution failed');
        }
        
        this.updateProgress(60, '📊 Extracting and processing results...');
        
        // Step 3: Get results
        const resultsResponse = await fetch(
            `${this.API_BASE}/results?session_id=${this.currentSessionId}&max_results=${maxResults}`
        );
        
        if (!resultsResponse.ok) {
            throw new Error(`Results failed: ${resultsResponse.status}`);
        }
        
        const resultsData = await resultsResponse.json();
        this.displayResults(resultsData, type);
        
        this.updateProgress(100, `✅ Found ${resultsData.count || 0} results!`);
        setTimeout(() => {
            document.getElementById('progress').style.display = 'none';
        }, 1500);
    }
    
    async executeFileSearch(file, maxResults) {
        // Step 1: Start session (same as URL search)
        await this.executeFullSearchStep1();
        
        this.updateProgress(40, '📤 Securely uploading your file...');
        
        // Step 2: Upload file
        const formData = new FormData();
        formData.append('file', file);
        formData.append('max_results', maxResults);
        
        const uploadResponse = await fetch(`${this.API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!uploadResponse.ok) {
            throw new Error(`Upload failed: ${uploadResponse.status}`);
        }
        
        const uploadData = await uploadResponse.json();
        if (uploadData.status !== 'success') {
            throw new Error(uploadData.error || 'File upload failed');
        }
        
        // Show upload info
        this.showUploadInfo(uploadData, file.name);
        this.updateProgress(50, '🔍 Searching with uploaded image...');
        
        // Step 3: Search with temp URL
        await this.executeFullSearch(uploadData.temp_url, 'url', maxResults);
    }
    
    async executeFullSearchStep1() {
        const startResponse = await fetch(`${this.API_BASE}/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const startData = await startResponse.json();
        if (startData.status !== 'success') {
            throw new Error(startData.error || 'Session initialization failed');
        }
        
        this.currentSessionId = startData.session_id;
        this.showSessionInfo(startData);
    }
    
    updateProgress(percent, text) {
        const progressFill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');
        
        progressFill.style.width = `${Math.min(percent, 100)}%`;
        progressText.textContent = text;
    }
    
    showSessionInfo(data) {
        const sessionInfo = document.getElementById('sessionInfo');
        sessionInfo.innerHTML = `
            <div class="session-card">
                <h3>🔐 Secure Session Active</h3>
                <div class="session-details">
                    <div class="detail-item">
                        <label>Session ID:</label>
                        <code>${data.session_id}</code>
                    </div>
                    <div class="detail-item">
                        <label>Status:</label>
                        <span class="status-badge success">${data.message}</span>
                    </div>
                    <div class="detail-item">
                        <label>Expires:</label>
                        <span>${new Date(data.expires_at).toLocaleString()}</span>
                    </div>
                </div>
                <small class="session-note">This session is encrypted and will auto-expire</small>
            </div>
        `;
        sessionInfo.style.display = 'block';
        sessionInfo.setAttribute('aria-live', 'polite');
    }
    
    showUploadInfo(data, originalName) {
        const uploadInfo = document.getElementById('uploadInfo');
        uploadInfo.innerHTML = `
            <div class="upload-card">
                <h3>📤 Upload Complete</h3>
                <div class="upload-details">
                    <div class="detail-item">
                        <label>Original File:</label>
                        <span>${originalName}</span>
                    </div>
                    <div class="detail-item">
                        <label>Size:</label>
                        <span>${this.formatFileSize(data.size_bytes)}</span>
                    </div>
                    <div class="detail-item">
                        <label>Secure URL:</label>
                        <a href="${data.temp_url}" target="_blank" rel="noopener">${data.temp_url}</a>
                    </div>
                    <div class="detail-item">
                        <label>Expires:</label>
                        <span>${new Date(data.expires_at).toLocaleString()}</span>
                    </div>
                </div>
            </div>
        `;
        uploadInfo.style.display = 'block';
    }
    
    displayResults(data, searchType) {
        const resultsSection = document.getElementById('results');
        const emptyState = document.querySelector('.results-empty');
        
        if (data.status === 'success') {
            this.showStatus(`✅ Found ${data.count} similar images in ${searchType.toLowerCase()} search!`, 'success');
            
            if (data.results && data.results.length > 0) {
                emptyState.style.display = 'none';
                resultsSection.innerHTML = `
                    <header class="results-header">
                        <h2>Search Results</h2>
                        <div class="results-meta">
                            <span class="meta-item">${data.count} images found</span>
                            <span class="meta-item">${searchType} search</span>
                            <span class="meta-item">${data.failed_thumbnails || 0} images unavailable</span>
                        </div>
                    </header>
                    <div class="results-grid" role="list">
                        ${data.results.map((result, index) => `
                            <article class="result-card" role="listitem">
                                <img 
                                    src="${result.thumbnail}" 
                                    alt="${result.description}" 
                                    class="result-image"
                                    loading="${index < 6 ? 'eager' : 'lazy'}"
                                    onerror="this.src='/static/images/placeholder.svg'; this.alt='Image unavailable'"
                                />
                                <div class="result-content">
                                    <h3 class="result-title">${this.truncateText(result.description, 120)}</h3>
                                    <div class="result-meta">
                                        <span class="meta-site">${result.sourceSite}</span>
                                    </div>
                                    <a href="${result.pageLink}" 
                                       target="_blank" 
                                       rel="noopener noreferrer"
                                       class="result-link"
                                       aria-label="View full page on ${result.sourceSite}">
                                        🔗 View on ${result.sourceSite}
                                    </a>
                                </div>
                            </article>
                        `).join('')}
                    </div>
                `;
                
                // Production: Lazy load images
                if ('IntersectionObserver' in window) {
                    const imageObserver = new IntersectionObserver((entries, observer) => {
                        entries.forEach(entry => {
                            if (entry.isIntersecting) {
                                const img = entry.target;
                                img.src = img.dataset.src || img.src;
                                img.classList.remove('lazy');
                                observer.unobserve(img);
                            }
                        });
                    });
                    
                    document.querySelectorAll('.result-image').forEach(img => {
                        if (!img.complete) {
                            imageObserver.observe(img);
                        }
                    });
                }
                
            } else {
                emptyState.style.display = 'block';
                emptyState.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">🔍</div>
                        <h2>No results found</h2>
                        <p>No similar images were found for your ${searchType.toLowerCase()} search. Try a different image or adjust your search.</p>
                        <button class="btn-secondary" onclick="app.resetSearch()">New Search</button>
                    </div>
                `;
            }
        } else {
            this.showStatus(`❌ ${data.error || 'Search failed. Please try again.'}`, 'error');
            emptyState.style.display = 'block';
            emptyState.innerHTML = `
                <div class="empty-state error-state">
                    <div class="empty-icon">⚠️</div>
                    <h2>Search Error</h2>
                    <p>${data.error || 'An unexpected error occurred.'}</p>
                    <button class="btn-secondary" onclick="app.resetSearch()">Try Again</button>
                </div>
            `;
        }
    }
    
    showStatus(message, type = 'info') {
        const status = document.getElementById('status');
        status.textContent = message;
        status.className = `status-message ${type} show`;
        status.setAttribute('role', 'alert');
        status.setAttribute('aria-live', 'assertive');
        
        // Auto-dismiss non-error messages
        if (type !== 'error') {
            setTimeout(() => {
                status.classList.remove('show');
            }, 5000);
        }
    }
    
    showEmptyState() {
        const results = document.getElementById('results');
        const emptyState = document.querySelector('.results-empty') || 
                          document.createElement('div');
        emptyState.className = 'results-empty';
        emptyState.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🔍</div>
                <h2>Ready to search</h2>
                <p>Paste an image URL or upload a file to begin your reverse image search. Our system uses secure, encrypted sessions for privacy.</p>
            </div>
        `;
        results.innerHTML = '';
        results.appendChild(emptyState);
        emptyState.style.display = 'block';
    }
    
    resetSearchState() {
        this.currentSessionId = null;
        document.getElementById('sessionInfo').style.display = 'none';
        document.getElementById('uploadInfo').style.display = 'none';
        document.getElementById('status').classList.remove('show');
        this.searchInProgress = false;
    }
    
    isValidUrl(string) {
        try {
            const url = new URL(string);
            return url.protocol === 'http:' || url.protocol === 'https:';
        } catch {
            return false;
        }
    }
    
    truncateText(text, maxLength) {
        return text.length > maxLength ? text.slice(0, maxLength).trim() + '...' : text;
    }
    
    handleKeyboard(e) {
        if (this.searchInProgress) return;
        
        // Enter in URL input
        if (e.key === 'Enter' && document.activeElement.id === 'urlInput') {
            e.preventDefault();
            this.searchByUrl({ preventDefault: () => {} });
        }
        
        // Ctrl+Enter in file input area
        if (e.key === 'Enter' && e.ctrlKey && 
            (document.activeElement.id === 'fileUpload' || 
             document.activeElement.closest('#fileTab'))) {
            e.preventDefault();
            this.searchByFile({ preventDefault: () => {} });
        }
        
        // Escape to reset
        if (e.key === 'Escape') {
            this.resetSearchState();
            this.showEmptyState();
            document.querySelector('.tab-btn.active').focus();
        }
    }
    
    focusFirstInput() {
        // Focus first available input
        const firstInput = document.querySelector('#urlInput');
        if (firstInput) {
            firstInput.focus();
            firstInput.setAttribute('autofocus', true);
        }
    }
    
    preloadImages() {
        // Production: Preload critical images
        const criticalImages = [
            '/static/images/placeholder.svg',
            'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzAwIiBoZWlnaHQ9IjE4MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjBmMGYwIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPkltYWdlIGxvYWRpbmc8L3RleHQ+PC9zdmc+'
        ];
        
        criticalImages.forEach(src => {
            const img = new Image();
            img.src = src;
        });
    }
    
    showApiDocs() {
        // Production: Show inline API docs
        const docs = document.createElement('div');
        docs.className = 'api-docs';
        docs.innerHTML = `
            <div class="modal-overlay" onclick="this.remove()">
                <div class="modal-content" onclick="event.stopPropagation()">
                    <h2>API Documentation</h2>
                    <div class="api-section">
                        <h3>Endpoints</h3>
                        <ul>
                            <li><strong>GET/POST /start</strong> - Initialize search session (10/min)</li>
                            <li><strong>POST /search</strong> - Upload image (5/min)</li>
                            <li><strong>GET /results</strong> - Extract results (5/min)</li>
                            <li><strong>GET/POST /full-search</strong> - Complete flow (3/min)</li>
                            <li><strong>POST /upload</strong> - File upload (10/min)</li>
                        </ul>
                    </div>
                    <div class="api-section">
                        <h3>Example Usage</h3>
                        <pre><code>curl -X POST http://{{ request.host }}/full-search \\
  -H "Content-Type: application/json" \\
  -d '{"type":"url","value":"https://example.com/image.jpg"}'</code></pre>
                    </div>
                    <button class="btn-close" onclick="this.closest('.modal-content').parentElement.remove()">Close</button>
                </div>
            </div>
        `;
        document.body.appendChild(docs);
    }
}

// Production: Error boundary
window.addEventListener('error', (e) => {
    console.error('Global error:', e.error);
    // In production, send to error tracking service
});

// Production: Performance monitoring
if ('performance' in window) {
    window.addEventListener('load', () => {
        const navigation = performance.getEntriesByType('navigation')[0];
        console.log('Navigation timing:', {
            type: navigation.type,
            duration: Math.round(navigation.loadEventEnd - navigation.loadEventStart),
            transferSize: navigation.transferSize
        });
    });
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new ReverseImageSearch();
    
    // Production: Service Worker registration
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js')
            .then(reg => console.log('SW registered:', reg))
            .catch(err => console.log('SW registration failed:', err));
    }
});

// Production: Handle page visibility
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        // Pause any ongoing operations
        if (window.app && window.app.searchInProgress) {
            console.log('Page hidden during search');
        }
    }
});
