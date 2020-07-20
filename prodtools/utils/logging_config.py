
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
        'brief': {
            'format': '%(levelname)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'DEBUG',
            'formatter': 'brief',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',  # Default is stderr
        },
        'file': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'prodtools.log',
            'maxBytes': 512000,
            'backupCount': 20,
        },
        'file_tm': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': 'tm_prodtools.log',
            'when': 'D',
            'interval': 1,
            'backupCount': 30,
        },
    },
    'loggers': {
        '': {  # root logger
            'handlers': ['default', 'file', 'file_tm', ],
            'level': 'DEBUG',
            'propagate': True,
        },
    }
}
