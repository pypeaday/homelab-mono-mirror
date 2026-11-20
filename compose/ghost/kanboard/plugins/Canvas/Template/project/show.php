<div class="page-header">
    <h2><?= $this->text->e($project['name']) ?> · <?= t('Canvas') ?></h2>
</div>

<div id="canvas-toolbar">
    <button type="button" id="canvas-autolayout" class="btn"><?= t('Auto layout') ?></button>
    <button type="button" id="canvas-group-lane" class="btn"><?= t('Group by lane') ?></button>
    <button type="button" id="canvas-group-column" class="btn"><?= t('Group by column') ?></button>
    <button type="button" id="canvas-add-note" class="btn"><?= t('+ Note') ?></button>
    <button type="button" id="canvas-reset" class="btn"><?= t('Reset positions') ?></button>
    <span class="canvas-hint"><?= t('Drag cards to arrange — positions persist. Double-click a card to open it.') ?></span>
    <span class="canvas-legend">
        <span style="background:#78909c"></span><?= t('Backlog') ?>
        <span style="background:#42a5f5"></span><?= t('Ready') ?>
        <span style="background:#ffa726"></span><?= t('WIP') ?>
        <span style="background:#66bb6a"></span><?= t('Done/closed') ?>
        <em><?= t('dashed purple border = agent-ready · red arrow = blocks · blue = parent/child · green = fixes · grey dashed = relates · yellow = note (dbl-click to edit)') ?></em>
    </span>
</div>
<div id="canvas-network"
     data-data-url="<?= $this->text->e($this->url->href('CanvasController', 'data', array('plugin' => 'canvas', 'project_id' => $project['id']))) ?>"
     data-save-url="<?= $this->text->e($this->url->href('CanvasController', 'save', array('plugin' => 'canvas', 'project_id' => $project['id']))) ?>"
     data-notes-url="<?= $this->text->e($this->url->href('CanvasController', 'saveNotes', array('plugin' => 'canvas', 'project_id' => $project['id']))) ?>"
     data-csrf="<?= $this->text->e($this->app->getToken()->getReusableCSRFToken()) ?>"></div>
