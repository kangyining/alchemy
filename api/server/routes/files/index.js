const express = require('express');
const {
  createFileLimiters,
  configMiddleware,
  requireJwtAuth,
  uaParser,
  checkBan,
} = require('~/server/middleware');
const { avatar: asstAvatarRouter } = require('~/server/routes/assistants/v1');
const { avatar: agentAvatarRouter } = require('~/server/routes/agents/v1');
const { createMulterInstance } = require('./multer');

const files = require('./files');
const images = require('./images');
const avatar = require('./avatar');
const speech = require('./speech');

const initialize = async () => {
  const router = express.Router();
  
  // MCP PDF downloads - public access (no auth required)
  const fs = require('fs').promises;
  const path = require('path');
  const { logger } = require('@librechat/data-schemas');
  
  router.get('/mcp/pdf/:filename', async (req, res) => {
    try {
      const { filename } = req.params;
      logger.debug(`MCP PDF download requested: ${filename}`);

      // Sanitize filename to prevent directory traversal
      const sanitizedFilename = path.basename(filename);
      if (sanitizedFilename !== filename) {
        return res.status(400).send('Invalid filename');
      }

      const pdfPath = path.join('/app/pdf-output', sanitizedFilename);
      
      // Check if file exists
      try {
        await fs.access(pdfPath);
      } catch (error) {
        logger.error(`PDF file not found: ${pdfPath}`);
        return res.status(404).send('File not found');
      }

      res.setHeader('Content-Type', 'application/pdf');
      res.setHeader('Content-Disposition', `attachment; filename="${sanitizedFilename}"`);
      
      const fileStream = await fs.readFile(pdfPath);
      res.send(fileStream);
    } catch (error) {
      logger.error('Error downloading MCP PDF:', error);
      res.status(500).send('Error downloading file');
    }
  });
  
  router.use(requireJwtAuth);
  router.use(configMiddleware);
  router.use(checkBan);
  router.use(uaParser);

  const upload = await createMulterInstance();
  router.post('/speech/stt', upload.single('audio'));

  /* Important: speech route must be added before the upload limiters */
  router.use('/speech', speech);

  const { fileUploadIpLimiter, fileUploadUserLimiter } = createFileLimiters();
  router.post('*', fileUploadIpLimiter, fileUploadUserLimiter);
  router.post('/', upload.single('file'));
  router.post('/images', upload.single('file'));
  router.post('/images/avatar', upload.single('file'));
  router.post('/images/agents/:agent_id/avatar', upload.single('file'));
  router.post('/images/assistants/:assistant_id/avatar', upload.single('file'));

  router.use('/', files);
  router.use('/images', images);
  router.use('/images/avatar', avatar);
  router.use('/images/agents', agentAvatarRouter);
  router.use('/images/assistants', asstAvatarRouter);
  return router;
};

module.exports = { initialize };
