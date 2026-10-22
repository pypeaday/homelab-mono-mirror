<?php

namespace Kanboard\Plugin\Canvas;

use Kanboard\Core\Plugin\Base;

class Plugin extends Base
{
    public function initialize()
    {
        $this->route->addRoute('canvas/:project_id', 'CanvasController', 'show', 'plugin');
        $this->route->addRoute('canvas/:project_id/data', 'CanvasController', 'data', 'plugin');
        $this->route->addRoute('canvas/:project_id/save', 'CanvasController', 'save', 'plugin');
        $this->route->addRoute('canvas/:project_id/notes', 'CanvasController', 'saveNotes', 'plugin');

        $this->template->hook->attach('template:project-header:view-switcher', 'canvas:project_header/views');

        $this->hook->on('template:layout:js', array('template' => 'plugins/Canvas/Asset/Javascript/vis/vis.min.js'));
        $this->hook->on('template:layout:js', array('template' => 'plugins/Canvas/Asset/Javascript/Canvas.js'));
        $this->hook->on('template:layout:css', array('template' => 'plugins/Canvas/Asset/Javascript/vis/vis.min.css'));
        $this->hook->on('template:layout:css', array('template' => 'plugins/Canvas/Asset/css/canvas.css'));
    }

    public function getPluginName()
    {
        return 'Canvas';
    }

    public function getPluginAuthor()
    {
        return 'nic + devin';
    }

    public function getPluginVersion()
    {
        return '0.1.0';
    }

    public function getPluginDescription()
    {
        return t('Freeform canvas view of project tasks with dependency arrows');
    }

    public function getPluginHomepage()
    {
        return 'https://git.paynepride.com/nic/homelab-mono';
    }

    public function getCompatibleVersion()
    {
        return '>=1.2.10';
    }
}
