// Production GET-First Reverse Image Search
// Optimized for browser URLs, shareability, and performance

class ReverseImageSearch {
    constructor() {
        this.API_BASE = window.location.origin;
        this.currentSessionId = null;
        this.searchInProgress = false;
        this.searchType = 'url';
        
        // DOM elements
        this.elements = {
            container: document.querySelector('.container'),
            urlInput: document.getElementById('urlInput'),
            fileInput: document.getElementById('fileUpload'),
            urlSearchBtn: document.getElementById('urlSearchBtn'),
            fileSearchBtn: document.getElementById('fileSearchBtn'),
            maxResults: document.getElementById('maxResults'),
            fileMaxResults: document.getElementById('fileMaxResults'),
            progress: document.getElementById('progress'),
            progressFill: document.getElementById('progressFill'),
            progressText: document.getElementById('progressText'),
            status: document.getElementById('status'),
            sessionInfo: document.getElementById('sessionInfo'),
            uploadInfo: document.getElementById('uploadInfo'),
            results: document.getElementById('results')
        };
        
        this.initializeEventListeners();
        this.showEmptyState();
        this.focusFirstInput();
        this.preloadCriticalResources();
        this.initializeFromURL();
    }
    
    initializeEventListeners() {
        // Tab switching
        document.querySelectorAll('.tab-btn').forEach((btn, index) => {
            btn.addEventListener('click', (e) => this.switchTab(e.currentTarget.dataset.tab || index));
            btn.dataset.tab = btn.textContent.trim().split(' ')[1].toLowerCase(); // 'URL Search' -> 'url'
        });
        
        // Form handling
        document.querySelector('.search-form').addEventListener('submit', (e) => e.preventDefault());
        
        // URL search
        this.elements.urlInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.searchByUrl();
            }
        });
        
        // File upload
        this.initializeFileUpload();
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));
        
        // Network status
        window.addEventListener('online', () => this.showStatus('✅ Connection restored', 'success'));
        window.addEventListener('offline', () => this.showStatus('⚠️ No internet connection', 'warning'));
        
        // Window resize
        window.addEventListener('resize', () => this.handleResize());
    }
    
    async switchTab(tab) {
        if (this.searchInProgress) return;
        
        // Update active states
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
            btn.setAttribute('aria-selected', 'false');
        });
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        
        const activeBtn = document.querySelector(`[data-tab="${tab}"]`) || 
                         Array.from(document.querySelectorAll('.tab-btn')).find(btn => 
                            btn.textContent.toLowerCase().includes(tab));
        
        if (activeBtn) {
            activeBtn.classList.add('active');
            activeBtn.setAttribute('aria-selected', 'true');
        }
        
        const activeTab = document.getElementById(`${tab}Tab`);
        if (activeTab) {
            activeTab.classList.add('active');
        }
        
        // Focus management
        const focusTarget = tab === 'url' ? this.elements.urlInput : this.elements.fileInput;
        focusTarget?.focus();
        
        // Reset state
        this.resetSearchState();
        this.showEmptyState();
        this.searchType = tab;
    }
    
    initializeFileUpload() {
        const dropzone = document.querySelector('.file-dropzone');
        const fileInput = this.elements.fileInput;
        const preview = document.getElementById('filePreview');
        const fileName = document.getElementById('fileName');
        const searchBtn = this.elements.fileSearchBtn;
        
        // Click to upload
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
            if (files.length > 0) {
                // Create synthetic file input event
                const dt = new DataTransfer();
                Array.from(files).forEach(f => dt.items.add(f));
                fileInput.files = dt.files;
                fileInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });
    }
    
    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    handleFileSelect(file, preview, fileName, searchBtn) {
        // Validation
        if (!file.type.startsWith('image/')) {
            this.showStatus('❌ Please select an image file (JPG, PNG, GIF, WebP)', 'error');
            return;
        }
        
        if (file.size > 8 * 1024 * 1024) {
            this.showStatus('❌ File too large. Maximum 8MB allowed.', 'error');
            return;
        }
        
        // Preview
        const reader = new FileReader();
        reader.onload = (e) => {
            preview.querySelector('img').src = e.target.result;
            preview.style.display = 'block';
        };
        reader.readAsDataURL(file);
        
        // Update UI
        fileName.textContent = file.name;
        preview.parentElement.parentElement.classList.add('has-file');
        searchBtn.disabled = false;
        searchBtn.querySelector('.btn-text').textContent = '🔍 Search';
        
        this.showStatus(`✅ Ready: ${file.name} (${this.formatFileSize(file.size)})`, 'success');
    }
    
    resetFileInput(preview, fileName, searchBtn) {
        this.elements.fileInput.value = '';
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
    
    async searchByUrl() {
        const url = this.elements.urlInput.value.trim();
        const maxResults = Math.min(parseInt(this.elements.maxResults.value), 50);
        
        if (!url || !this.isValidUrl(url)) {
            this.showStatus('❌ Please enter a valid URL starting with http:// or https://', 'error');
            this.elements.urlInput.focus();
            return;
        }
        
        if (this.searchInProgress) return;
        
        // Create GET URL
        const searchUrl = new URL(`${this.API_BASE}/full-search`);
        searchUrl.searchParams.set('type', 'url');
        searchUrl.searchParams.set('value', url);
        searchUrl.searchParams.set('max_results', maxResults);
        
        await this.executeGetSearch(searchUrl.toString(), 'URL');
    }
    
    async searchByFile() {
        const file = this.elements.fileInput.files[0];
        const maxResults = Math.min(parseInt(this.elements.fileMaxResults.value), 50);
        
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
        this.searchType = type;
        
        const progress = this.elements.progress;
        const progressFill = this.elements.progressFill;
        const progressText = this.elements.progressText;
        
        progress.style.display = 'block';
        progressFill.style.width = '0%';
        progressText.textContent = `🔍 Starting ${type.toLowerCase()} search...`;
        
        try {
            await searchFunction();
        } catch (error) {
            console.error(`${type} search error:`, error);
            this.showStatus(`❌ ${type} search failed: ${error.message}`, 'error');
        } finally {
            this.searchInProgress = false;
            setTimeout(() => {
                progress.style.display = 'none';
                progressFill.style.width = '0%';
            }, 1500);
        }
    }
    
    async executeGetSearch(searchUrl, type) {
        const progressText = this.elements.progressText;
        progressText.textContent = `🔍 Searching ${type.toLowerCase()}...`;
        
        try {
            // Production GET request
            const response = await fetch(searchUrl, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                cache: 'no-cache'  // Fresh results
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.displayResults(data, type);
                
                // Update URL for bookmarking (URL searches only)
                if (type === 'URL') {
                    const newUrl = new URL(searchUrl);
                    if (data.session_id) {
                        newUrl.searchParams.set('session_id', data.session_id);
                    }
                    window.history.replaceState({ searchUrl }, '', newUrl.toString());
                }
                
                this.showStatus(`✅ Found ${data.results?.length || 0} results!`, 'success');
            } else {
                throw new Error(data.error || 'Search failed');
            }
            
        } catch (error) {
            console.error('GET search error:', error);
            this.showStatus(`❌ ${error.message}`, 'error');
        }
    }
    
    async executeFileSearch(file, maxResults) {
        // Step 1: Upload file
        this.updateProgress(25, '📤 Securely uploading your file...');
        
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
            throw new Error(uploadData.error || 'Upload failed');
        }
        
        this.showUploadInfo(uploadData, file.name);
        this.updateProgress(50, '🔍 Searching with your uploaded image...');
        
        // Step 2: GET search with temp URL
        const searchUrl = new URL(`${this.API_BASE}/full-search`);
        searchUrl.searchParams.set('type', 'url');
        searchUrl.searchParams.set('value', uploadData.temp_url);
        searchUrl.searchParams.set('max_results', maxResults);
        
        await this.executeGetSearch(searchUrl.toString(), 'File');
    }
    
    updateProgress(percent, text) {
        const progressFill = this.elements.progressFill;
        const progressText = this.elements.progressText;
        
        progressFill.style.width = `${Math.min(percent, 100)}%`;
        progressText.textContent = text;
    }
    
    showSessionInfo(data) {
        this.elements.sessionInfo.innerHTML = `
            <div class="session-card">
                <h3>🔐 Search Session Active</h3>
                <div class="session-details">
                    <div class="detail-row">
                        <span class="detail-label">ID:</span>
                        <code class="detail-value">${data.session_id}</code>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Status:</span>
                        <span class="status-badge success">${data.message}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Expires:</span>
                        <span class="detail-value">${new Date(data.expires_at).toLocaleString()}</span>
                    </div>
                </div>
            </div>
        `;
        this.elements.sessionInfo.style.display = 'block';
        this.elements.sessionInfo.setAttribute('aria-live', 'polite');
    }
    
    showUploadInfo(data, originalName) {
        this.elements.uploadInfo.innerHTML = `
            <div class="upload-card">
                <h3>📤 File Uploaded Successfully</h3>
                <div class="upload-details">
                    <div class="detail-row">
                        <span class="detail-label">Original:</span>
                        <span class="detail-value">${originalName}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Size:</span>
                        <span class="detail-value">${this.formatFileSize(data.size_bytes)}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Secure URL:</span>
                        <a href="${data.temp_url}" target="_blank" rel="noopener" class="detail-value detail-link">
                            ${data.temp_url}
                        </a>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Expires:</span>
                        <span class="detail-value">${new Date(data.expires_at).toLocaleString()}</span>
                    </div>
                </div>
            </div>
        `;
        this.elements.uploadInfo.style.display = 'block';
    }
    
    displayResults(data, searchType) {
        const resultsSection = this.elements.results;
        const emptyState = resultsSection.querySelector('.results-empty') || 
                          document.createElement('div');
        emptyState.className = 'results-empty';
        
        if (data.status === 'success') {
            this.showStatus(`✅ Found ${data.count || 0} similar images!`, 'success');
            
            if (data.results && data.results.length > 0) {
                emptyState.style.display = 'none';
                resultsSection.innerHTML = `
                    <header class="results-header">
                        <h2 aria-live="polite">Search Results</h2>
                        <div class="results-meta">
                            <span class="meta-item">${data.count} images found</span>
                            <span class="meta-item">${searchType} search</span>
                            ${data.failed_thumbnails ? `<span class="meta-item warning">${data.failed_thumbnails} unavailable</span>` : ''}
                        </div>
                    </header>
                    <div class="results-grid" role="list">
                        ${data.results.map((result, index) => `
                            <article class="result-card" role="listitem" tabindex="0">
                                <img 
                                    src="${result.thumbnail}" 
                                    alt="${this.escapeHtml(result.description)}" 
                                    class="result-image"
                                    loading="${index < 6 ? 'eager' : 'lazy'}"
                                    height="200"
                                    width="100%"
                                    onerror="this.onerror=null; this.src='/static/images/placeholder.svg'; this.alt='Image unavailable'"
                                />
                                <div class="result-content">
                                    <h3 class="result-title">${this.truncateText(result.description, 120)}</h3>
                                    <div class="result-meta">
                                        <span class="meta-site" aria-label="Source">${this.escapeHtml(result.sourceSite)}</span>
                                    </div>
                                    <a href="${this.escapeHtml(result.pageLink)}" 
                                       target="_blank" 
                                       rel="noopener noreferrer"
                                       class="result-link"
                                       aria-label="View full page on ${this.escapeHtml(result.sourceSite)}">
                                        🔗 View on ${this.escapeHtml(result.sourceSite)}
                                    </a>
                                </div>
                            </article>
                        `).join('')}
                    </div>
                `;
                
                // Keyboard navigation for results
                document.querySelectorAll('.result-card').forEach((card, index) => {
                    card.addEventListener('keydown', (e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            card.querySelector('.result-link')?.click();
                        }
                    });
                });
                
                // Lazy loading with IntersectionObserver
                this.initializeLazyLoading();
                
            } else {
                emptyState.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">🔍</div>
                        <h2>No Results Found</h2>
                        <p>No similar images were found for your ${searchType.toLowerCase()} search.</p>
                        <div class="empty-actions">
                            <button class="btn-secondary" onclick="app.resetSearch()">New Search</button>
                            <button class="btn-outline" onclick="app.tryDifferent()">Try Different Image</button>
                        </div>
                    </div>
                `;
                emptyState.style.display = 'block';
                resultsSection.innerHTML = '';
                resultsSection.appendChild(emptyState);
            }
        } else {
            this.showStatus(`❌ ${data.error || 'Search failed'}`, 'error');
            emptyState.innerHTML = `
                <div class="empty-state error-state">
                    <div class="empty-icon">⚠️</div>
                    <h2>Search Error</h2>
                    <p>${data.error || 'An unexpected error occurred.'}</p>
                    <div class="empty-actions">
                        <button class="btn-secondary" onclick="app.resetSearch()">Try Again</button>
                        <a href="/health" target="_blank" class="btn-outline">Check Status</a>
                    </div>
                </div>
            `;
            emptyState.style.display = 'block';
            resultsSection.innerHTML = '';
            resultsSection.appendChild(emptyState);
        }
    }
    
    initializeLazyLoading() {
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        if (img.dataset.src) {
                            img.src = img.dataset.src;
                            img.removeAttribute('data-src');
                        }
                        img.classList.remove('lazy');
                        imageObserver.unobserve(img);
                    }
                });
            }, {
                rootMargin: '50px'
            });
            
            document.querySelectorAll('img.lazy').forEach(img => {
                imageObserver.observe(img);
            });
        }
    }
    
    showStatus(message, type = 'info') {
        const status = this.elements.status;
        status.textContent = message;
        status.className = `status-message ${type} show`;
        status.setAttribute('role', 'alert');
        status.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite');
        
        if (type !== 'error') {
            setTimeout(() => status.classList.remove('show'), 5000);
        }
    }
    
    showEmptyState() {
        const results = this.elements.results;
        const emptyState = document.createElement('div');
        emptyState.className = 'results-empty';
        emptyState.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🔍</div>
                <h2>Ready to Search</h2>
                <p>Enter an image URL above or switch to the upload tab to begin your reverse image search.</p>
                <p class="empty-hint"><strong>Pro Tip:</strong> Bookmark this page - your searches are shareable!</p>
            </div>
        `;
        results.innerHTML = '';
        results.appendChild(emptyState);
    }
    
    resetSearchState() {
        this.currentSessionId = null;
        this.elements.sessionInfo.style.display = 'none';
        this.elements.uploadInfo.style.display = 'none';
        this.elements.status.classList.remove('show');
        this.searchInProgress = false;
        this.elements.urlSearchBtn.disabled = false;
        this.elements.fileSearchBtn.disabled = true;
    }
    
    isValidUrl(string) {
        try {
            const url = new URL(string.startsWith('http') ? string : 'https://' + string);
            return url.protocol === 'http:' || url.protocol === 'https:';
        } catch {
            return false;
        }
    }
    
    truncateText(text, maxLength) {
        if (!text) return '';
        return text.length > maxLength ? `${text.slice(0, maxLength).trim()}...` : text;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    handleKeyboard(e) {
        if (this.searchInProgress) return;
        
        // Enter in URL input
        if (e.key === 'Enter' && document.activeElement === this.elements.urlInput) {
            e.preventDefault();
            this.searchByUrl();
        }
        
        // Ctrl+Enter for file search
        if (e.key === 'Enter' && e.ctrlKey && document.activeElement.closest('#fileTab')) {
            e.preventDefault();
            this.searchByFile();
        }
        
        // Escape to reset
        if (e.key === 'Escape') {
            e.preventDefault();
            this.resetSearchState();
            this.showEmptyState();
            document.querySelector('.tab-btn.active').focus();
        }
    }
    
    handleResize() {
        // Production: Handle responsive layout changes
        const resultsGrid = document.querySelector('.results-grid');
        if (resultsGrid) {
            // Recalculate grid if needed
            resultsGrid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(300px, 1fr))';
        }
    }
    
    focusFirstInput() {
        // Focus URL input by default
        this.elements.urlInput.focus();
    }
    
    preloadCriticalResources() {
        // Preload essential images
        const criticalImages = [
            '/static/images/placeholder.svg',
            'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjBmMGYwIiBvcGFjaXR5PSIwLjMiLz48L3N2Zz4='
        ];
        
        criticalImages.forEach(src => {
            const link = document.createElement('link');
            link.rel = 'preload';
            link.as = 'image';
            link.href = src;
            document.head.appendChild(link);
        });
    }
    
    initializeFromURL() {
        // Auto-search from URL parameters
        const urlParams = new URLSearchParams(window.location.search);
        const value = urlParams.get('value') || urlParams.get('url');
        const type = urlParams.get('type') || 'url';
        
        if (value && (type === 'url' || type === 'file')) {
            this.showStatus('🔍 Auto-starting search from URL...', 'info');
            
            const maxResults = parseInt(urlParams.get('max_results') || '20');
            
            setTimeout(() => {
                if (type === 'url' && this.isValidUrl(value)) {
                    this.elements.urlInput.value = value;
                    this.elements.maxResults.value = maxResults;
                    this.searchByUrl();
                }
                // File auto-search would need the temp URL
            }, 800);
        }
    }
}

// Global app instance
let app;

document.addEventListener('DOMContentLoaded', () => {
    app = new ReverseImageSearch();
    
    // Production: Performance monitoring
    if (performance && performance.mark) {
        performance.mark('app-ready');
    }
    
    // Service Worker (progressive web app)
    if ('serviceWorker' in navigator && location.protocol === 'https:') {
        navigator.serviceWorker.register('/sw.js')
            .then(reg => console.log('SW registered'))
            .catch(err => console.log('SW failed:', err));
    }
});

// Global error handling
window.addEventListener('error', (e) => {
    console.error('Global error:', e.error);
    // Production: Send to error tracking
    if (app) {
        app.showStatus('⚠️ An unexpected error occurred', 'error');
    }
});

// Handle page visibility
document.addEventListener('visibilitychange', () => {
    if (document.hidden && app?.searchInProgress) {
        console.log('Search paused - tab hidden');
    }
});

// Export for template access
window.app = app;
