const API_BASE = window.location.origin;
let socket = null;
let devices = [];
let deviceStatus = {}; // Track connection status per device
let isStreaming = false;
let currentEditIndex = null;

// Waveform visualization
let waveformCanvas, waveformCtx;
let waveformData = [];
let audioLevel = 0;
let animationId = null;

// Initialize application
document.addEventListener('DOMContentLoaded', () => {
    initializeWebSocket();
    initializeWaveform();
    loadDevices();
    loadAudioDevices();
    setupEventListeners();
    checkStreamStatus();
});

// Initialize Waveform Canvas
function initializeWaveform() {
    waveformCanvas = document.getElementById('waveformCanvas');
    waveformCtx = waveformCanvas.getContext('2d');

    // Handle resize
    const resizeCanvas = () => {
        const parent = waveformCanvas.parentElement;
        waveformCanvas.width = parent.offsetWidth;
        waveformCanvas.height = parent.offsetHeight;
    };

    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    // Start animation loop
    animateWaveform();
}

function animateWaveform() {
    if (!waveformCtx) return;

    const width = waveformCanvas.width;
    const height = waveformCanvas.height;
    const centerY = height / 2;

    // Clear canvas
    waveformCtx.fillStyle = 'rgba(255, 255, 255, 1)'; // Light fade
    waveformCtx.fillRect(0, 0, width, height);

    if (isStreaming && waveformData.length > 0) {
        // Create gradient (Dark for light theme)
        const gradient = waveformCtx.createLinearGradient(0, 0, width, 0);
        gradient.addColorStop(0, '#0051ffff');
        gradient.addColorStop(0.5, '#4b5563'); // Medium Gray
        gradient.addColorStop(1, '#0051ffff');

        waveformCtx.beginPath();
        waveformCtx.strokeStyle = gradient;
        waveformCtx.lineWidth = 3;
        waveformCtx.lineJoin = 'round';
        waveformCtx.lineCap = 'round';

        // Shadow
        waveformCtx.shadowBlur = 10;
        waveformCtx.shadowColor = 'rgba(0, 0, 0, 0.1)';

        // Draw mirrored waveform
        const sliceWidth = width / waveformData.length;
        let x = 0;

        // Top half
        waveformCtx.moveTo(0, centerY);
        for (let i = 0; i < waveformData.length; i++) {
            const v = waveformData[i] * 1.5; // Amplify slightly
            const y = centerY - (v * centerY * 0.8); // Scale to 80% of half height

            // Smooth curve
            if (i === 0) waveformCtx.moveTo(x, y);
            else {
                const prevX = x - sliceWidth;
                const prevY = centerY - (waveformData[i - 1] * 1.5 * centerY * 0.8);
                const cpX = (prevX + x) / 2;
                waveformCtx.quadraticCurveTo(prevX, prevY, cpX, (prevY + y) / 2);
            }
            x += sliceWidth;
        }
        waveformCtx.lineTo(width, centerY);

        // Bottom half (mirror)
        x = width;
        for (let i = waveformData.length - 1; i >= 0; i--) {
            const v = waveformData[i] * 1.5;
            const y = centerY + (v * centerY * 0.8);
            x -= sliceWidth;
            waveformCtx.lineTo(x, y);
        }

        waveformCtx.closePath();
        waveformCtx.stroke();

        // Fill with low opacity dark
        waveformCtx.fillStyle = 'rgba(0, 81, 255, 1)';
        waveformCtx.fill();

        // Reset shadow for performance
        waveformCtx.shadowBlur = 0;

        // Update volume bar
        const volumePercent = Math.min(audioLevel * 120, 100); // Boost visual level slightly
        document.getElementById('volumeBar').style.width = `${volumePercent}%`;
        document.getElementById('volumePercent').textContent = `${Math.round(volumePercent)}%`;
    } else {
        // Idle state - gentle pulse line
        waveformCtx.beginPath();
        waveformCtx.strokeStyle = 'rgba(0, 0, 0, 0.1)';
        waveformCtx.lineWidth = 1;
        waveformCtx.moveTo(0, centerY);
        waveformCtx.lineTo(width, centerY);
        waveformCtx.stroke();

        waveformData = [];
        audioLevel = 0;
        document.getElementById('volumeBar').style.width = '0%';
        document.getElementById('volumePercent').textContent = '0%';
    }

    animationId = requestAnimationFrame(animateWaveform);
}

// WebSocket for real-time logs and device status
function initializeWebSocket() {
    socket = io(`${API_BASE}/logs`);

    socket.on('connect', () => {
        console.log('WebSocket connected');
        showToast('Connected to server', 'success');
    });

    socket.on('disconnect', () => {
        console.log('WebSocket disconnected');
        showToast('Disconnected from server', 'error');
    });

    socket.on('log_message', (data) => {
        addLog(data.message);

        // Parse ACK messages to update device status
        if (data.message.includes('Received ACK from')) {
            const deviceName = data.message.split('Received ACK from ')[1];
            updateDeviceStatus(deviceName, 'connected');
        } else if (data.message.includes('No response from')) {
            const deviceName = data.message.split('No response from ')[1];
            updateDeviceStatus(deviceName, 'timeout');
        }
    });

    // Receive real-time audio levels from backend
    socket.on('audio_level', (data) => {
        if (data.values && data.values.length > 0) {
            // Normalize audio samples to 0-1 range (absolute value)
            waveformData = data.values.map(v => Math.abs(v) / 32768.0);
        }
        audioLevel = data.rms || 0;
    });

    // Receive device status updates (buffer full, etc.)
    socket.on('device_status', (data) => {
        if (data.device && data.status) {
            updateDeviceStatus(data.device, data.status);
        }
    });

    loadInitialLogs();
}

async function loadInitialLogs() {
    try {
        const response = await fetch(`${API_BASE}/api/logs`);
        const logs = await response.json();

        const container = document.getElementById('logsContainer');
        container.innerHTML = '';

        logs.forEach(log => addLog(log));
    } catch (error) {
        console.error('Error loading logs:', error);
    }
}

function addLog(message) {
    const container = document.getElementById('logsContainer');
    const entry = document.createElement('div');
    entry.className = 'text-black text-xs leading-relaxed hover:text-black/80 transition-colors font-mono';

    // Timestamp
    const time = new Date().toLocaleTimeString([], { hour12: false });
    entry.innerHTML = `<span class="text-black/60 mr-2">[${time}]</span>${escapeHtml(message)}`;

    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;

    // Limit log entries
    while (container.children.length > 100) {
        container.removeChild(container.firstChild);
    }
}

// Device status tracking
function updateDeviceStatus(deviceName, status) {
    deviceStatus[deviceName] = {
        status: status,
        lastUpdate: Date.now()
    };
    renderDevices();
}

function getDeviceStatusColor(deviceName) {
    if (!isStreaming) {
        return '#10b981'; // Green - Ready
    }

    const status = deviceStatus[deviceName];
    if (!status) return '#fbbf24'; // Yellow - Waiting

    const timeSinceUpdate = Date.now() - status.lastUpdate;
    if (timeSinceUpdate > 5000) return '#ef4444'; // Red - Timeout

    if (status.status === 'buffer_full') return '#f97316'; // Orange - Buffer Full
    if (status.status === 'connected') return '#10b981'; // Green - Streaming active

    return '#fbbf24'; // Yellow - Default
}

function getDeviceStatusText(deviceName) {
    if (!isStreaming) return 'Ready';

    const status = deviceStatus[deviceName];
    if (!status) return 'Waiting...';

    const timeSinceUpdate = Date.now() - status.lastUpdate;
    if (timeSinceUpdate > 5000) return 'Disconnected';

    if (status.status === 'buffer_full') return 'Buffer Full';
    if (status.status === 'connected') return 'Streaming';

    return 'Waiting...';
}

// Event Listeners
function setupEventListeners() {
    document.getElementById('startBtn').addEventListener('click', startStreaming);
    document.getElementById('stopBtn').addEventListener('click', stopStreaming);
    document.getElementById('scanBtn').addEventListener('click', scanDevices);
    document.getElementById('addDeviceBtn').addEventListener('click', () => openModal('addDeviceModal'));
    document.getElementById('saveDeviceBtn').addEventListener('click', saveNewDevice);
    document.getElementById('updateDeviceBtn').addEventListener('click', updateDevice);
    document.getElementById('clearLogsBtn').addEventListener('click', clearLogs);

    // Noise Reduction Toggle
    document.getElementById('noiseReductionToggle').addEventListener('change', toggleNoiseReduction);

    // Logs toggle
    document.getElementById('logsToggle').addEventListener('click', () => {
        const content = document.getElementById('logsContent');
        const chevron = document.getElementById('logsChevron');
        content.classList.toggle('hidden');
        chevron.classList.toggle('rotate-180');
    });

    // Form enter key handling
    ['deviceName', 'deviceIP', 'devicePort'].forEach(id => {
        document.getElementById(id)?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') saveNewDevice();
        });
    });
}

// Noise Reduction Control
async function toggleNoiseReduction(e) {
    const enabled = e.target.checked;

    try {
        const response = await fetch(`${API_BASE}/api/noise-reduction`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });

        const result = await response.json();

        if (result.success) {
            showToast(`Noise reduction ${enabled ? 'enabled' : 'disabled'}`, 'info');
        } else {
            showToast(result.error || 'Failed to toggle noise reduction', 'error');
            // Revert toggle if failed
            e.target.checked = !enabled;
        }
    } catch (error) {
        console.error('Error toggling noise reduction:', error);
        showToast('Error toggling noise reduction', 'error');
        e.target.checked = !enabled;
    }
}

// Device Management
async function loadDevices() {
    try {
        const response = await fetch(`${API_BASE}/api/devices`);
        devices = await response.json();
        renderDevices();
    } catch (error) {
        console.error('Error loading devices:', error);
        showToast('Error loading devices', 'error');
    }
}

// Audio Device Management
async function loadAudioDevices() {
    try {
        const response = await fetch(`${API_BASE}/api/audio-devices`);
        const devicesData = await response.json();

        const select = document.getElementById('audioDeviceSelect');
        select.innerHTML = '<option value="">Select an audio device...</option>';

        devicesData.forEach(device => {
            const option = document.createElement('option');
            option.value = device.index;
            option.textContent = `${device.name} (${device.is_virtual ? 'Virtual' : 'Physical'})`;
            select.appendChild(option);
        });

        // Auto-select first physical device
        if (devicesData.length > 0) {
            const physicalDevice = devicesData.find(d => !d.is_virtual);
            if (physicalDevice) {
                select.value = physicalDevice.index;
            } else if (devicesData.length > 0) {
                select.value = devicesData[0].index;
            }
        }
    } catch (error) {
        console.error('Error loading audio devices:', error);
        showToast('Error loading audio devices', 'error');
    }
}

function renderDevices() {
    const container = document.getElementById('deviceList');
    const countEl = document.getElementById('deviceCount');

    countEl.textContent = `${devices.length} Active`;

    if (devices.length === 0) {
        container.innerHTML = `
            <div class="col-span-full flex flex-col items-center justify-center py-12 text-gray-500">
                <div class="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-4">
                    <svg class="w-8 h-8 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
                </div>
                <p>No devices connected</p>
            </div>`;
        return;
    }

    container.innerHTML = devices.map((device, index) => {
        const statusColor = getDeviceStatusColor(device.name);
        const statusText = getDeviceStatusText(device.name);
        const isStreamingActive = statusText === 'Streaming';

        return `
        <div class="glass-panel p-5 rounded-2xl flex flex-col gap-4 transition-all duration-300 ${isStreamingActive ? 'ring-2 ring-offset-2 ring-offset-transparent' : ''}" style="${isStreamingActive ? `box-shadow: 0 0 30px ${statusColor}40;` : ''}">
            <!-- Header: Device Info + Actions -->
            <div class="flex items-start justify-between">
                <div class="flex items-center gap-3 flex-1">
                    <div class="flex-1 min-w-0">
                        <h3 class="font-semibold text-base text-black truncate">${escapeHtml(device.name)}</h3>
                        <p class="text-xs text-black/50 font-mono mt-0.5">${escapeHtml(device.ip)}:${device.port}</p>
                    </div>
                </div>
                
                <div class="flex gap-1.5 opacity-60 hover:opacity-100 transition-opacity">
                    <button onclick="editDevice(${index})" class="p-2 text-black/70 hover:text-black hover:bg-black/5 rounded-lg transition-all hover:scale-110" title="Edit">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>
                    </button>
                    <button onclick="deleteDevice(${index})" class="p-2 text-black/70 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all hover:scale-110" title="Delete">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                    </button>
                </div>
            </div>
            
            <!-- Status Badge -->
            <div class="flex items-center justify-between pt-3 border-t border-black/5">
                <span class="text-xs font-medium text-black/50 uppercase tracking-wider">Status</span>
                <div class="flex items-center gap-2.5 px-4 py-2 rounded-full transition-all" style="background: ${statusColor}15; border: 1.5px solid ${statusColor}30;">
                    <div class="relative flex items-center justify-center">
                        <div class="w-2 h-2 rounded-full" style="background-color: ${statusColor}"></div>
                        ${isStreamingActive ? `<div class="absolute inset-0 w-2 h-2 rounded-full animate-ping" style="background-color: ${statusColor}"></div>` : ''}
                    </div>
                    <span class="text-sm font-semibold" style="color: ${statusColor}">${statusText}</span>
                </div>
            </div>
        </div>
        `;
    }).join('');
}

async function saveNewDevice() {
    const name = document.getElementById('deviceName').value.trim();
    const ip = document.getElementById('deviceIP').value.trim();
    const port = parseInt(document.getElementById('devicePort').value);

    if (!name || !ip || !port) {
        showToast('Please fill in all fields', 'info');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/devices`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, ip, port })
        });

        const result = await response.json();

        if (result.success) {
            showToast(`Device added: ${name}`, 'success');
            devices = result.devices;
            renderDevices();
            closeModal('addDeviceModal');

            document.getElementById('deviceName').value = '';
            document.getElementById('deviceIP').value = '';
            document.getElementById('devicePort').value = '6666';
        } else {
            showToast(result.error || 'Failed to add device', 'error');
        }
    } catch (error) {
        console.error('Error adding device:', error);
        showToast('Error adding device', 'error');
    }
}

function editDevice(index) {
    currentEditIndex = index;
    const device = devices[index];

    document.getElementById('editDeviceName').value = device.name;
    document.getElementById('editDeviceIP').value = device.ip;
    document.getElementById('editDevicePort').value = device.port;

    openModal('editDeviceModal');
}

async function updateDevice() {
    if (currentEditIndex === null) return;

    const name = document.getElementById('editDeviceName').value.trim();
    const ip = document.getElementById('editDeviceIP').value.trim();
    const port = parseInt(document.getElementById('editDevicePort').value);

    if (!name || !ip || !port) {
        showToast('Please fill in all fields', 'info');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/devices/${currentEditIndex}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, ip, port })
        });

        const result = await response.json();

        if (result.success) {
            showToast(`Device updated: ${name}`, 'success');
            devices = result.devices;
            renderDevices();
            closeModal('editDeviceModal');
            currentEditIndex = null;
        } else {
            showToast(result.error || 'Failed to update device', 'error');
        }
    } catch (error) {
        console.error('Error updating device:', error);
        showToast('Error updating device', 'error');
    }
}

async function deleteDevice(index) {
    const device = devices[index];

    if (!confirm(`Delete device "${device.name}"?`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/devices/${index}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            showToast(`Device deleted: ${device.name}`, 'success');
            delete deviceStatus[device.name];
            devices = result.devices;
            renderDevices();
        } else {
            showToast(result.error || 'Failed to delete device', 'error');
        }
    } catch (error) {
        console.error('Error deleting device:', error);
        showToast('Error deleting device', 'error');
    }
}

async function scanDevices() {
    openModal('scanModal');

    const resultsContainer = document.getElementById('scanResults');
    resultsContainer.innerHTML = `
        <div class="text-center py-12">
            <div class="inline-block w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mb-4"></div>
            <p class="text-gray-400">Scanning network for devices...</p>
            <p class="text-gray-500 text-sm mt-2">This may take a few seconds</p>
        </div>
    `;

    try {
        const response = await fetch(`${API_BASE}/api/devices/scan`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success && result.devices.length > 0) {
            resultsContainer.innerHTML = `
                <h4 class="font-medium mb-4 text-white">Found ${result.devices.length} device(s)</h4>
                <div class="space-y-2">
                    ${result.devices.map((device, index) => `
                        <div class="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/5">
                            <div>
                                <h4 class="font-medium text-white text-sm">${escapeHtml(device.name)}</h4>
                                <p class="text-xs text-gray-400 font-mono">${escapeHtml(device.ip)}:${device.port}</p>
                            </div>
                            <button onclick="addScannedDevice(${index})" class="px-3 py-1.5 bg-primary hover:bg-indigo-600 text-white rounded-lg text-sm font-medium transition-colors">
                                Add
                            </button>
                        </div>
                    `).join('')}
                </div>
            `;

            window.scannedDevices = result.devices;
        } else {
            resultsContainer.innerHTML = `
                <div class="text-center py-8">
                    <p class="text-gray-500">No devices found on the network</p>
                    <p class="text-gray-600 text-sm mt-2">
                        Make sure devices are powered on and connected to the same network
                    </p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error scanning devices:', error);
        resultsContainer.innerHTML = `
            <div class="text-center py-8 text-red-400">
                Error scanning for devices
            </div>
        `;
    }
}

async function addScannedDevice(index) {
    const device = window.scannedDevices[index];

    try {
        const response = await fetch(`${API_BASE}/api/devices`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(device)
        });

        const result = await response.json();

        if (result.success) {
            showToast(`Device added: ${device.name}`, 'success');
            devices = result.devices;
            renderDevices();
            closeModal('scanModal');
        } else {
            showToast(result.error || 'Failed to add device', 'error');
        }
    } catch (error) {
        console.error('Error adding scanned device:', error);
        showToast('Error adding device', 'error');
    }
}

// Streaming Control
async function startStreaming() {
    if (devices.length === 0) {
        showToast('Please add at least one device before streaming', 'info');
        return;
    }

    const deviceSelect = document.getElementById('audioDeviceSelect');
    const deviceIndex = parseInt(deviceSelect.value);

    if (!deviceIndex && deviceIndex !== 0) {
        showToast('Please select an audio input device', 'info');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/stream/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_index: deviceIndex })
        });

        const result = await response.json();

        if (result.success) {
            isStreaming = true;
            deviceStatus = {}; // Reset status
            updateStreamingUI(true);
            showToast('Streaming started', 'success');
        } else {
            showToast(result.error || 'Failed to start streaming', 'error');
        }
    } catch (error) {
        console.error('Error starting stream:', error);
        showToast('Error starting streaming', 'error');
    }
}

async function stopStreaming() {
    try {
        const response = await fetch(`${API_BASE}/api/stream/stop`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            isStreaming = false;
            deviceStatus = {}; // Clear status
            updateStreamingUI(false);
            showToast('Streaming stopped', 'info');
            renderDevices();
        } else {
            showToast(result.error || 'Failed to stop streaming', 'error');
        }
    } catch (error) {
        console.error('Error stopping stream:', error);
        showToast('Error stopping streaming', 'error');
    }
}

async function checkStreamStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/stream/status`);
        const status = await response.json();

        isStreaming = status.active;
        updateStreamingUI(status.active);
    } catch (error) {
        console.error('Error checking stream status:', error);
    }
}

function updateStreamingUI(streaming) {
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const statusDot = document.getElementById('statusDot');
    const statusPing = document.getElementById('statusPing');
    const statusText = document.getElementById('statusText');

    if (streaming) {
        startBtn.disabled = true;
        stopBtn.disabled = false;

        statusDot.classList.remove('bg-gray-400');
        statusDot.classList.add('bg-green-500', 'shadow-sm');
        statusPing.classList.remove('opacity-0');
        statusPing.classList.add('bg-green-500');

        statusText.textContent = 'Broadcasting Live';
        statusText.classList.add('text-green-600');
    } else {
        startBtn.disabled = false;
        stopBtn.disabled = true;

        statusDot.classList.add('bg-gray-400');
        statusDot.classList.remove('bg-green-500', 'shadow-sm');
        statusPing.classList.add('opacity-0');
        statusPing.classList.remove('bg-green-500');

        statusText.textContent = 'System Ready';
        statusText.classList.remove('text-green-600');
    }
}

// Modal Management
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    modal.classList.remove('hidden');
    // Small delay to allow display:block to apply before opacity transition
    setTimeout(() => {
        modal.querySelector('.glass-card').classList.remove('scale-95', 'opacity-0');
        modal.querySelector('.glass-card').classList.add('scale-100', 'opacity-100');
    }, 10);
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    const card = modal.querySelector('.glass-card');

    card.classList.remove('scale-100', 'opacity-100');
    card.classList.add('scale-95', 'opacity-0');

    setTimeout(() => {
        modal.classList.add('hidden');
    }, 200);
}

// Toast Notification System
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');

    let icon = '';
    let typeClass = '';

    switch (type) {
        case 'success':
            icon = '<svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>';
            typeClass = 'toast-success';
            break;
        case 'error':
            icon = '<svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>';
            typeClass = 'toast-error';
            break;
        default:
            icon = '<svg class="w-5 h-5 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>';
            typeClass = 'toast-info';
    }

    toast.className = `toast ${typeClass}`;
    toast.innerHTML = `${icon}<span class="text-sm font-medium">${escapeHtml(message)}</span>`;

    container.appendChild(toast);

    // Auto remove
    setTimeout(() => {
        toast.classList.add('hiding');
        toast.addEventListener('animationend', () => {
            toast.remove();
        });
    }, 3000);
}

// Utility Functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function clearLogs() {
    const container = document.getElementById('logsContainer');
    container.innerHTML = '<div class="text-primary text-xs">Logs cleared</div>';
}

// Periodic status check and device updates
setInterval(() => {
    checkStreamStatus();
    if (isStreaming) {
        renderDevices(); // Update device status colors
    }
}, 2000);
