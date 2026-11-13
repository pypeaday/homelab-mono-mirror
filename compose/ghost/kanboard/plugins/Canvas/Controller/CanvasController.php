<?php

namespace Kanboard\Plugin\Canvas\Controller;

use Kanboard\Controller\BaseController;
use Kanboard\Model\TaskModel;

class CanvasController extends BaseController
{
    private static $COLUMN_COLORS = array(
        'backlog'           => '#78909c',
        'ready'             => '#42a5f5',
        'work in progress'  => '#ffa726',
        'done'              => '#66bb6a',
    );

    private static $EDGE_COLORS = array(
        'blocks'            => '#e53935',
        'is blocked by'     => '#e53935',
        'is a parent of'    => '#1e88e5',
        'is a child of'     => '#1e88e5',
        'targets milestone' => '#8e24aa',
        'is a milestone of' => '#8e24aa',
        'fixes'             => '#43a047',
        'is fixed by'       => '#43a047',
    );

    private static $EDGE_DIRECTION = array(
        'blocks'            => 1,
        'is a parent of'    => 1,
        'targets milestone' => 1,
        'fixes'             => 1,
        'is blocked by'     => -1,
        'is a child of'     => -1,
        'is a milestone of' => -1,
        'is fixed by'       => -1,
    );

    public function data()
    {
        $project = $this->getProject();
        $this->response->json($this->buildGraph($project));
    }

    public function show()
    {
        $project = $this->getProject();

        $this->response->html($this->helper->layout->app('canvas:project/show', array(
            'project' => $project,
            'title'   => $project['name'].' · '.t('Canvas'),
        )));
    }

    private function buildGraph(array $project)
    {
        $columns = array();
        foreach ($this->columnModel->getAll($project['id']) as $column) {
            $columns[$column['id']] = $column['title'];
        }

        $lanes = array();
        foreach ($this->swimlaneModel->getAll($project['id']) as $swimlane) {
            $lanes[$swimlane['id']] = $swimlane['name'];
        }

        $tasks = array_merge(
            $this->taskFinderModel->getAll($project['id'], TaskModel::STATUS_OPEN),
            $this->taskFinderModel->getAll($project['id'], TaskModel::STATUS_CLOSED)
        );

        $nodes = array();
        $edges = array();
        $seenLinks = array();
        $users = array();

        foreach ($tasks as $task) {
            $metadata = $this->taskMetadataModel->getAll($task['id']);
            $x = null;
            $y = null;
            if (! empty($metadata['canvas_pos'])) {
                $xy = explode(',', $metadata['canvas_pos']);
                if (count($xy) === 2) {
                    $x = (float) $xy[0];
                    $y = (float) $xy[1];
                }
            }

            $tags = array();
            foreach ($this->taskTagModel->getTagsByTask($task['id']) as $tag) {
                $tags[] = $tag['name'];
            }

            $owner = '';
            if (! empty($task['owner_id'])) {
                if (! isset($users[$task['owner_id']])) {
                    $u = $this->userModel->getById($task['owner_id']);
                    $users[$task['owner_id']] = $u ? ($u['name'] ?: $u['username']) : '';
                }
                $owner = $users[$task['owner_id']];
            }

            $columnTitle = isset($columns[$task['column_id']]) ? $columns[$task['column_id']] : '?';
            $closed = (int) $task['is_active'] === 0;
            $fill = isset(self::$COLUMN_COLORS[strtolower($columnTitle)])
                ? self::$COLUMN_COLORS[strtolower($columnTitle)]
                : '#90a4ae';
            if ($closed) {
                $fill = '#66bb6a';
            }

            $nodes[] = array(
                'id'      => (int) $task['id'],
                'title'   => $task['title'],
                'column'  => $columnTitle,
                'lane'    => isset($lanes[$task['swimlane_id']]) ? $lanes[$task['swimlane_id']] : '',
                'tags'    => $tags,
                'owner'   => $owner,
                'closed'  => $closed,
                'fill'    => $fill,
                'due'     => ! empty($task['date_due']) ? date('Y-m-d', $task['date_due']) : '',
                'done_on' => ! empty($task['date_completed']) ? date('Y-m-d', $task['date_completed']) : '',
                'url'     => $this->helper->url->to('TaskViewController', 'show', array(
                    'task_id'    => $task['id'],
                    'project_id' => $project['id'],
                )),
                'x' => $x,
                'y' => $y,
            );

            foreach ($this->taskLinkModel->getAllGroupedByLabel($task['id']) as $label => $links) {
                foreach ($links as $link) {
                    if (isset($seenLinks[$link['id']])) {
                        continue;
                    }
                    $seenLinks[$link['id']] = true;
                    $edges[] = $this->normalizeEdge($label, (int) $task['id'], (int) $link['task_id']);
                }
            }
        }

        $projectMeta = $this->projectMetadataModel->getAll($project['id']);
        $notes = array();
        if (! empty($projectMeta['canvas_notes'])) {
            $decoded = json_decode($projectMeta['canvas_notes'], true);
            if (is_array($decoded)) {
                $notes = $decoded;
            }
        }

        return array(
            'nodes'   => $nodes,
            'edges'   => $edges,
            'columns' => array_values($columns),
            'lanes'   => array_values($lanes),
            'notes'   => $notes,
        );
    }

    public function saveNotes()
    {
        $this->checkReusableCSRFParam();
        $project = $this->getProject();
        $notes = json_decode($this->request->getStringParam('notes', '[]'), true);

        $clean = array();
        if (is_array($notes)) {
            foreach ($notes as $note) {
                if (! isset($note['id'], $note['text'])) {
                    continue;
                }
                $clean[] = array(
                    'id'    => substr(preg_replace('/[^a-z0-9_]/i', '', (string) $note['id']), 0, 40),
                    'text'  => mb_substr((string) $note['text'], 0, 2000),
                    'x'     => isset($note['x']) ? (float) $note['x'] : 0,
                    'y'     => isset($note['y']) ? (float) $note['y'] : 0,
                );
            }
        }

        $this->projectMetadataModel->save($project['id'], array('canvas_notes' => json_encode(array_values($clean))));
        $this->response->text('ok');
    }

    public function save()
    {
        $this->checkReusableCSRFParam();
        $project = $this->getProject();
        $taskId = (int) $this->request->getStringParam('task_id');
        $task = $this->taskFinderModel->getById($taskId);

        if ($task && (int) $task['project_id'] === (int) $project['id']) {
            $x = $this->request->getStringParam('x');
            $y = $this->request->getStringParam('y');
            $value = ($x === '' || $y === '') ? '' : round((float) $x).','.round((float) $y);
            $this->taskMetadataModel->save($taskId, array('canvas_pos' => $value));
        }

        $this->response->text('ok');
    }

    private function normalizeEdge($label, $from, $to)
    {
        $directed = isset(self::$EDGE_DIRECTION[$label]);
        $dir = $directed ? self::$EDGE_DIRECTION[$label] : 0;
        $color = isset(self::$EDGE_COLORS[$label]) ? self::$EDGE_COLORS[$label] : '#9e9e9e';

        return array(
            'from'     => $dir === -1 ? $to : $from,
            'to'       => $dir === -1 ? $from : $to,
            'label'    => $label,
            'color'    => $color,
            'directed' => $directed,
        );
    }
}
