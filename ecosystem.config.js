module.exports = {
    apps: [{
        name: 'flask-server',
        script: 'app.py',
        interpreter: '/Users/usmanayobami/Documents/document-extrator/extract/env/bin/python',
        instances: 1,
        autorestart: true,
        watch: false,
        max_memory_restart: '500M',
        env: {
            PORT: 5001,
            NODE_ENV: 'production'
        },
        error_file: './logs/pm2-error.log',
        out_file: './logs/pm2-out.log',
        log_file: './logs/pm2-combined.log',
        time: true
    }]
};

