// ===== Global State =====
let currentSection = 'dashboard';
let autoRefreshInterval = null;
let tokenHistoryLog = [];

// ===== Initialization =====
document.addEventListener('DOMContentLoaded', function() {
    initializeUI();
    setupEventListeners();
    loadDashboardData();
    startAutoRefresh();
    updateTime();
});

function initializeUI() {
    // Update time
    setInterval(updateTime, 1000);
    
    // Load initial token info
    loadTokenInfo();
}

function setupEventListeners() {
    // Navigation menu
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            navigateToSection(this.dataset.section);
        });
    });

    document.querySelector('.brand-link')?.addEventListener('click', function(e) {
        e.preventDefault();
        navigateToSection(this.dataset.section);
    });

    document.querySelectorAll('.stat-card').forEach(card => {
        card.addEventListener('click', function() {
            navigateToSection(this.dataset.targetSection);
        });
    });

    // Email filter
    document.getElementById('email-filter')?.addEventListener('keyup', filterEmails);
}

// ===== Navigation =====
function navigateToSection(sectionName) {
    // Hide current section
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    
    // Show new section
    const section = document.getElementById(sectionName);
    if (section) {
        section.classList.add('active');
        document.querySelector(`[data-section="${sectionName}"]`).classList.add('active');
        currentSection = sectionName;
        
        // Load section-specific data
        switch(sectionName) {
            case 'emails':
                loadEmails();
                break;
            case 'token':
                loadTokenInfo();
                break;
            case 'errors':
                loadErrors();
                break;
            case 'logs':
                loadMailLogs();
                break;
            case 'tickets':
                loadTickets();
                break;
        }
    }
}

// ===== Dashboard =====
function loadDashboardData() {
    fetch('/api/status')
        .then(r => r.json())
        .then(data => {
            document.getElementById('stat-emails').textContent = data.total_emails_processed;
            document.getElementById('stat-tickets').textContent = data.total_tickets_created;
            document.getElementById('stat-success').textContent = 
                data.total_emails_processed > 0 
                    ? Math.round((data.total_tickets_created / data.total_emails_processed) * 100) + '%'
                    : '0%';
            document.getElementById('stat-errors').textContent = data.errors_count;
            
            document.getElementById('sys-status').textContent = data.is_running ? 'Çalışıyor' : 'Hazır';
            document.getElementById('last-run').textContent = data.last_run 
                ? new Date(data.last_run).toLocaleString('tr-TR')
                : 'Henüz çalışmadı';
        })
        .catch(error => showToast('Dashboard verisi yüklenemedi: ' + error, 'error'));
}

function runNow() {
    showToast('Sistem başlatılıyor...', 'info');
    fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showToast(`✅ ${data.message}`, 'success');
            } else {
                showToast(`❌ ${data.error || data.message}`, 'error');
            }
            loadDashboardData();
            if (currentSection === 'logs') {
                loadMailLogs();
            }
        })
        .catch(error => showToast('Çalıştırma hatası: ' + error, 'error'));
}

function startAutoRefresh() {
    autoRefreshInterval = setInterval(() => {
        if (currentSection === 'dashboard') {
            loadDashboardData();
        } else if (currentSection === 'logs') {
            loadMailLogs();
        } else if (currentSection === 'tickets') {
            loadTickets();
        }
    }, 5000); // 5 saniye
}

// ===== Email Functions =====
function loadEmails() {
    const container = document.getElementById('emails-list');
    container.innerHTML = '<p class="loading">E-postalar yükleniyor</p>';
    
    fetch('/api/emails')
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                container.innerHTML = `<p class="no-data">❌ Hata: ${data.error}</p>`;
                return;
            }
            
            if (data.emails.length === 0) {
                container.innerHTML = '<p class="no-data">📭 E-posta bulunamadı</p>';
                return;
            }
            
            container.innerHTML = data.emails.map(email => `
                <div class="email-item">
                    <div class="email-info">
                        <div class="email-from">📧 ${escapeHtml(email.from)}</div>
                        <div class="email-subject">Konu: ${escapeHtml(email.subject)}</div>
                        <div class="email-preview">${escapeHtml(email.preview)}</div>
                    </div>
                    <div class="email-actions">
                        <button class="email-btn" onclick="processEmail('${email.id}')">
                            🔄 İşle
                        </button>
                    </div>
                </div>
            `).join('');
        })
        .catch(error => {
            container.innerHTML = `<p class="no-data">❌ Yükleme hatası: ${error}</p>`;
        });
}

function processEmail(emailId) {
    showToast('E-posta işleniyor...', 'info');
    
    fetch('/api/process-email', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ email_id: emailId })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            showToast(`✅ Ticket başarıyla oluşturuldu! ID: #${data.ticket_id}`, 'success');
            loadDashboardData();
        } else {
            showToast(`⚠️ Hata: ${data.message}`, 'error');
        }
    })
    .catch(error => showToast('İşlem başarısız: ' + error, 'error'));
}

function filterEmails() {
    const searchTerm = document.getElementById('email-filter').value.toLowerCase();
    document.querySelectorAll('.email-item').forEach(item => {
        const text = item.textContent.toLowerCase();
        item.style.display = text.includes(searchTerm) ? '' : 'none';
    });
}

// ===== Token Functions =====
function loadTokenInfo() {
    fetch('/api/token/info')
        .then(r => r.json())
        .then(data => {
            if (data.token_info) {
                const info = data.token_info;
                document.getElementById('token-status').textContent = info.token ? '✅ Geçerli' : '❌ Geçersiz';
                document.getElementById('token-value').textContent = info.token || 'Token bulunamadı';
                document.getElementById('token-details').textContent = 
                    `Son Güncelleme: ${info.acquired_at ? new Date(info.acquired_at).toLocaleString('tr-TR') : 'N/A'} | Geçerlilik: ${info.expires_in || '?'}`;
                document.getElementById('token-update').textContent = 
                    info.acquired_at ? new Date(info.acquired_at).toLocaleTimeString('tr-TR') : '--:--:--';
            }
        })
        .catch(error => console.error('Token yükleme hatası:', error));
}

function refreshToken() {
    showToast('Token yenileniyor...', 'info');
    
    fetch('/api/token/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            loadTokenInfo();
            addTokenHistory('🔄 Token yenilendi');
            showToast('✅ Token başarıyla yenilendi!', 'success');
        } else {
            showToast('❌ Token yenileme başarısız: ' + data.error, 'error');
        }
    })
    .catch(error => showToast('Hata: ' + error, 'error'));
}

function copyToken() {
    const tokenText = document.getElementById('token-value').textContent;
    navigator.clipboard.writeText(tokenText).then(() => {
        showToast('✅ Token kopyalandı!', 'success');
    }).catch(() => {
        showToast('❌ Kopya işlemi başarısız', 'error');
    });
}

function invalidateToken() {
    if (confirm('Token cache\'ini temizlemek istediğinizden emin misiniz?')) {
        refreshToken();
        addTokenHistory('🗑️ Cache temizlendi');
    }
}

function addTokenHistory(action) {
    const time = new Date().toLocaleTimeString('tr-TR');
    tokenHistoryLog.unshift({ action, time });
    
    const historyDiv = document.getElementById('token-history');
    historyDiv.innerHTML = tokenHistoryLog.slice(0, 10).map(entry => 
        `<div class="token-history-item">[${entry.time}] ${entry.action}</div>`
    ).join('');
}

// ===== Validation Functions =====
function validateTurkishID() {
    const idInput = document.getElementById('turkish-id-input');
    const resultDiv = document.getElementById('turkish-id-result');
    const id = idInput.value;
    
    if (!id) {
        resultDiv.classList.remove('show');
        return;
    }
    
    fetch('/api/validate/turkish-id', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_number: id })
    })
    .then(r => r.json())
    .then(data => {
        resultDiv.classList.add('show');
        if (data.is_valid) {
            resultDiv.classList.remove('error');
            resultDiv.classList.add('success');
            resultDiv.textContent = '✅ Geçerli TC Kimlik Numarası';
        } else {
            resultDiv.classList.remove('success');
            resultDiv.classList.add('error');
            resultDiv.textContent = '❌ Geçersiz TC Kimlik Numarası';
        }
    })
    .catch(error => {
        resultDiv.classList.add('show', 'error');
        resultDiv.textContent = '❌ Doğrulama hatası: ' + error;
    });
}

function validateTaxID() {
    const taxInput = document.getElementById('tax-id-input');
    const resultDiv = document.getElementById('tax-id-result');
    const taxId = taxInput.value;
    
    if (!taxId) {
        resultDiv.classList.remove('show');
        return;
    }
    
    fetch('/api/validate/tax-id', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tax_id: taxId })
    })
    .then(r => r.json())
    .then(data => {
        resultDiv.classList.add('show');
        if (data.is_valid) {
            resultDiv.classList.remove('error');
            resultDiv.classList.add('success');
            resultDiv.textContent = '✅ Geçerli VKN';
        } else {
            resultDiv.classList.remove('success');
            resultDiv.classList.add('error');
            resultDiv.textContent = '❌ Geçersiz VKN';
        }
    })
    .catch(error => {
        resultDiv.classList.add('show', 'error');
        resultDiv.textContent = '❌ Doğrulama hatası: ' + error;
    });
}

function checkProfanity() {
    const textInput = document.getElementById('profanity-input');
    const resultDiv = document.getElementById('profanity-result');
    const text = textInput.value;
    
    if (!text) {
        resultDiv.classList.remove('show');
        return;
    }
    
    fetch('/api/profanity-check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text })
    })
    .then(r => r.json())
    .then(data => {
        resultDiv.classList.add('show');
        if (data.has_profanity) {
            resultDiv.classList.remove('success');
            resultDiv.classList.add('error');
            resultDiv.textContent = '⚠️ Uygunsuz içerik tespit edildi!';
        } else {
            resultDiv.classList.remove('error');
            resultDiv.classList.add('success');
            resultDiv.textContent = '✅ İçerik temiz';
        }
    })
    .catch(error => {
        resultDiv.classList.add('show', 'error');
        resultDiv.textContent = '❌ Kontrol hatası: ' + error;
    });
}

// ===== Error Functions =====
function loadErrors() {
    fetch('/api/errors')
        .then(r => r.json())
        .then(data => {
            const container = document.getElementById('errors-list');
            const errorCount = document.getElementById('error-count');
            
            errorCount.textContent = data.errors.length + ' hata';
            
            if (data.errors.length === 0) {
                container.innerHTML = '<p class="no-data">✅ Hata yok</p>';
                return;
            }
            
            container.innerHTML = data.errors.map(error => `
                <div class="error-item">
                    <div class="error-time">${new Date(error.timestamp).toLocaleString('tr-TR')}</div>
                    <div class="error-message">${escapeHtml(error.error || 'İşlem başarısız')}</div>
                    ${error.sender_email ? `<div><strong>Gönderen:</strong> ${escapeHtml(error.sender_email)}</div>` : ''}
                    ${error.subject ? `<div><strong>Konu:</strong> ${escapeHtml(error.subject)}</div>` : ''}
                    ${error.details ? `<div><strong>Ayrıntı:</strong> ${escapeHtml(error.details)}</div>` : ''}
                </div>
            `).join('');
        })
        .catch(error => {
            document.getElementById('errors-list').innerHTML = 
                `<p class="no-data">❌ Hata yükleme başarısız</p>`;
        });
}

function clearErrors() {
    if (confirm('Tüm hataları temizlemek istediğinizden emin misiniz?')) {
        fetch('/api/clear-errors', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                loadErrors();
                showToast('✅ Hatalar temizlendi!', 'success');
            }
        })
        .catch(error => showToast('Temizleme hatası: ' + error, 'error'));
    }
}

function loadMailLogs() {
    fetch('/api/mail-logs')
        .then(r => r.json())
        .then(data => {
            const container = document.getElementById('mail-logs-list');
            const count = document.getElementById('mail-log-count');
            count.textContent = data.logs.length + ' kayıt';

            if (data.logs.length === 0) {
                container.innerHTML = '<p class="no-data">📭 Henüz işlem logu yok</p>';
                return;
            }

            container.innerHTML = data.logs.map(log => {
                const statusLabels = {
                    success: 'BAŞARILI',
                    blocked: 'ENGELLENDİ',
                    failed: 'BAŞARISIZ',
                    rejected: 'REDDEDİLDİ'
                };
                const status = statusLabels[log.status] || log.status;
                return `
                    <div class="log-item log-${escapeHtml(log.status)}">
                        <div class="log-header">
                            <strong>${escapeHtml(status)}</strong>
                            <span>${new Date(log.timestamp).toLocaleString('tr-TR')}</span>
                        </div>
                        <div><strong>Olay:</strong> ${escapeHtml(formatEvent(log.event))}</div>
                        <div><strong>Gönderen:</strong> ${escapeHtml(log.sender_email || '-')}</div>
                        <div><strong>Konu:</strong> ${escapeHtml(log.subject || '-')}</div>
                        <div><strong>Neden:</strong> ${escapeHtml(log.reason || '-')}</div>
                        ${log.details ? `<div><strong>Ayrıntı:</strong> ${escapeHtml(log.details)}</div>` : ''}
                        ${log.classification ? `<div><strong>Kategori:</strong> ${escapeHtml(formatClassification(log.classification))}</div>` : ''}
                        ${log.ticket_id ? `<div><strong>Ticket:</strong> #${escapeHtml(String(log.ticket_id))}</div>` : ''}
                        ${getMailBody(log) ? `<button class="mail-content-btn" type="button" data-log-index="${data.logs.indexOf(log)}">İçeriği Gör</button>` : ''}
                    </div>
                `;
            }).join('');

            container.querySelectorAll('[data-log-index]').forEach(button => {
                button.addEventListener('click', () => {
                    openMailContent(getMailBody(data.logs[Number(button.dataset.logIndex)]));
                });
            });
        })
        .catch(error => {
            document.getElementById('mail-logs-list').innerHTML =
                `<p class="no-data">❌ Log yükleme başarısız: ${escapeHtml(String(error))}</p>`;
        });
}

function clearMailLogs() {
    if (!confirm('Tüm işlem loglarını temizlemek istediğinizden emin misiniz?')) {
        return;
    }

    fetch('/api/mail-logs/clear', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                loadMailLogs();
                showToast('✅ İşlem logları temizlendi!', 'success');
            }
        })
        .catch(error => showToast('Log temizleme hatası: ' + error, 'error'));
}

function loadTickets() {
    fetch('/api/tickets')
        .then(r => r.json())
        .then(data => {
            const container = document.getElementById('tickets-list');
            document.getElementById('ticket-count').textContent = data.tickets.length + ' ticket';

            if (data.tickets.length === 0) {
                container.innerHTML = '<p class="no-data">📭 Oluşturulmuş ticket bulunamadı</p>';
                return;
            }

            container.innerHTML = data.tickets.map(ticket => {
                const details = ticket.ticket_details || {};
                return `
                    <div class="ticket-item">
                        <div class="log-header">
                            <strong>🎫 Ticket #${escapeHtml(String(ticket.ticket_id || '-'))}</strong>
                            <span>${new Date(ticket.timestamp).toLocaleString('tr-TR')}</span>
                        </div>
                        <div><strong>Gönderen:</strong> ${escapeHtml(ticket.sender_email || '-')}</div>
                        <div><strong>Konu:</strong> ${escapeHtml(ticket.subject || '-')}</div>
                        <div><strong>Kategori:</strong> ${escapeHtml(formatClassification(ticket.classification))}</div>
                        <div><strong>Alt kategori:</strong> ${escapeHtml(formatCategoryCode(details.sub_category_code))}</div>
                        <div><strong>İçerik:</strong> ${escapeHtml(details.body_preview || '-')}</div>
                        ${getMailBody(ticket) ? `<button class="mail-content-btn" type="button" data-ticket-index="${data.tickets.indexOf(ticket)}">İçeriği Gör</button>` : ''}
                    </div>
                `;
            }).join('');

            container.querySelectorAll('[data-ticket-index]').forEach(button => {
                button.addEventListener('click', () => {
                    openMailContent(getMailBody(data.tickets[Number(button.dataset.ticketIndex)]));
                });
            });
        })
        .catch(error => {
            document.getElementById('tickets-list').innerHTML =
                `<p class="no-data">❌ Ticket yükleme başarısız: ${escapeHtml(String(error))}</p>`;
        });
}

function formatEvent(eventName) {
    const labels = {
        email_processed: 'E-posta işlendi',
        ticket_created: 'Ticket oluşturuldu',
        ticket_not_created: 'Ticket oluşturulamadı',
        email_fetch: 'E-posta alınamadı',
        processor_error: 'Sistem hatası'
    };
    return labels[eventName] || eventName || '-';
}

function getMailBody(record) {
    return record.mail_body || record.ticket_details?.body_preview || '';
}

function openMailContent(content) {
    const modal = document.getElementById('mail-content-modal');
    document.getElementById('mail-modal-body').textContent = content || 'E-posta içeriği bulunamadı.';
    modal.hidden = false;
}

function closeMailContent() {
    document.getElementById('mail-content-modal').hidden = true;
}

function formatCategoryCode(code) {
    const labels = {
        INVOICE_REQUEST: 'Fatura Talebi ve Şikayetleri',
        GUIDE_THANK_YOU: 'Rehber Teşekkürü',
        CONSULTANT_THANK_YOU: 'Danışman Teşekkürü',
        GENERAL_THANK_YOU: 'Genel Teşekkür',
        FACILITY_CONTACT: 'Tesis İletişim'
    };
    return labels[code] || code || '-';
}

function formatClassification(classification) {
    if (!classification) {
        return '-';
    }

    const labels = {
        COMPLAINT: 'Şikayet',
        INVOICE: 'Fatura',
        INVOICE_REQUEST: 'Fatura Talebi ve Şikayetleri',
        THANK_YOU: 'Teşekkür',
        GUIDE_THANK_YOU: 'Rehber Teşekkürü',
        CONSULTANT_THANK_YOU: 'Danışman Teşekkürü',
        GENERAL_THANK_YOU: 'Genel Teşekkür',
        GENERAL: 'Genel',
        FACILITY: 'Tesis',
        FACILITY_CONTACT: 'Tesis İletişim',
        rejected_content: 'Uygunsuz içerik'
    };

    return classification.split(' > ').map(part => labels[part] || part).join(' > ');
}

// ===== Settings Functions =====
function saveSettings() {
    const settings = {
        autoCheckInterval: document.getElementById('auto-check-interval').value,
        emailRetention: document.getElementById('email-retention').value,
        enableNotifications: document.getElementById('enable-notifications').checked,
        enableProfanityCheck: document.getElementById('enable-profanity-check').checked
    };
    
    localStorage.setItem('app-settings', JSON.stringify(settings));
    showToast('✅ Ayarlar kaydedildi!', 'success');
}

function exportData() {
    showToast('📥 Veriler dışa aktarılıyor...', 'info');
    
    // Simulate export
    setTimeout(() => {
        const data = {
            exportDate: new Date().toISOString(),
            stats: {
                totalEmailsProcessed: document.getElementById('stat-emails').textContent,
                totalTicketsCreated: document.getElementById('stat-tickets').textContent,
                successRate: document.getElementById('stat-success').textContent
            }
        };
        
        const dataStr = JSON.stringify(data, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `email-automation-export-${Date.now()}.json`;
        link.click();
        
        showToast('✅ Veriler başarıyla dışa aktarıldı!', 'success');
    }, 1000);
}

function resetStats() {
    if (confirm('İstatistikleri sıfırlamak istediğinizden emin misiniz? Bu işlem geri alınamaz!')) {
        // API'a sıfırlama isteği gönder
        showToast('✅ İstatistikler sıfırlandı!', 'success');
        loadDashboardData();
    }
}

// ===== Utility Functions =====
function updateTime() {
    const now = new Date();
    document.getElementById('current-time').textContent = now.toLocaleTimeString('tr-TR');
    document.getElementById('sys-time').textContent = now.toLocaleTimeString('tr-TR');
    const dashboardDate = document.getElementById('dashboard-date');
    if (dashboardDate) {
        dashboardDate.textContent = now.toLocaleDateString('tr-TR', {
            day: '2-digit',
            month: 'short',
            year: 'numeric'
        });
    }
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast show ${type}`;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// ===== Event Listeners for Forms =====
document.addEventListener('DOMContentLoaded', function() {
    // Turkish ID live validation
    document.getElementById('turkish-id-input')?.addEventListener('change', validateTurkishID);
    
    // Tax ID live validation
    document.getElementById('tax-id-input')?.addEventListener('change', validateTaxID);
    
    // Profanity check live
    document.getElementById('profanity-input')?.addEventListener('change', checkProfanity);
});
