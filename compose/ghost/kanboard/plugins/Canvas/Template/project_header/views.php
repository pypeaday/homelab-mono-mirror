<li <?= $this->app->checkMenuSelection('CanvasController') ?>>
    <?= $this->url->icon('share-alt', t('Canvas'), 'CanvasController', 'show', array(
        'project_id' => $project['id'],
        'plugin'     => 'canvas',
    ), false, 'view-canvas', t('Freeform canvas')) ?>
</li>
