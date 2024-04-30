# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division, print_function, unicode_literals)

import os
import sys
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2 import QtWidgets, QtCore, QtGui
from maya import OpenMayaUI as om
from shiboken2 import wrapInstance
import maya.cmds as cmds
from maya.api import OpenMaya as om2
import math
import random

# ClickableFrame クラスを定義
class ClickableFrame(QFrame):
    clicked = Signal()

    def __init__(self, parent=None):
        super(ClickableFrame, self).__init__(parent)
        self.text_edit = None

    def mousePressEvent(self, event):
        self.clicked.emit()

    def set_text_edit(self, text_edit):
        self.text_edit = text_edit

    def update_info_editor(self, *args):
        if self.text_edit:
            self.text_edit.clear()
            if args:
                for info in args:
                    if isinstance(info, list):
                        # リストの場合は文字列に変換して追加
                        self.text_edit.appendPlainText(str(info))
                    else:
                        self.text_edit.appendPlainText(info)
            else:
                self.text_edit.appendPlainText("No overlapping faces.")
        else:
            print("Error: 'text_edit' is None.")

# メインのクラス
class MainWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setObjectName("MainWindow")
        self.set_UI()
        #実行時に赤いマテリアルを作成
        self.create_red_material()
        #ハイライトされた情報を保存
        self.highlight_states = {}
        # 元のマテリアルを保存
        self.materials = {}

    # UI構成
    def set_UI(self):
        self.setWindowTitle("Search Overlap")
        self.setGeometry(1100, 500, 500, 200)
        self.setWindowFlags(QtCore.Qt.Tool)
        self.create_widgets()
        self.create_layout()
        self.create_connections()

    # ウィジェットを作成
    def create_widgets(self):
        self.addButton = QtWidgets.QPushButton("Add")
        self.removeButton = QtWidgets.QPushButton("Remove")
        self.search_button = QtWidgets.QPushButton("Search")
        self.refreshButton = QtWidgets.QPushButton("Refresh")
        self.select_enable_CheckBox = QtWidgets.QCheckBox("Enable Select ", self)
        self.infoeditor = ClickableFrame(self)
        self.infoeditor.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.infoeditor.setLayout(QVBoxLayout())
        self.infoeditor.layout().addWidget(QLabel("info Editor"))
        self.infoeditor.setVisible(True)
        self.text_editor = QPlainTextEdit(self)
        self.text_editor.setReadOnly(True)
        self.text_editor.setVisible(False)
        self.infoeditor.set_text_edit(self.text_editor)

    # レイアウトの作成
    def create_layout(self):
        self.whole_layout = QtWidgets.QVBoxLayout()
        scroll_area = QtWidgets.QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.whole_layout.addWidget(scroll_area)
        self.centralWidget = QtWidgets.QWidget()
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.gridLayout = QtWidgets.QGridLayout(self.centralWidget)
        self.gridLayout.addWidget(self.list)

        self.bottom_layout = QtWidgets.QHBoxLayout()
        self.bottom_layout.addWidget(self.addButton)
        self.bottom_layout.addWidget(self.removeButton)
        self.bottom_layout.addWidget(self.search_button)
        self.bottom_layout.addWidget(self.refreshButton)
        self.bottom_layout.addWidget(self.select_enable_CheckBox)

        scroll_area.setWidget(self.centralWidget)
        self.whole_layout.addWidget(self.infoeditor)
        self.whole_layout.addWidget(self.text_editor)

        self.whole_layout.addLayout(self.bottom_layout)
        self.setLayout(self.whole_layout)

    # 接続の作成
    def create_connections(self):
        self.addButton.clicked.connect(self.addButton_onClicked)
        self.removeButton.clicked.connect(self.removeButton_onClicked)
        self.refreshButton.clicked.connect(self.refreshButton_onClicked)
        self.select_enable_CheckBox.stateChanged.connect(self.select_enable)
        self.search_button.clicked.connect(self.search_button_onClicked)
        self.infoeditor.clicked.connect(self.toggle_text_editor)
        self.list.itemSelectionChanged.connect(self.list_selection_changed)

    # addButtonの関数
    def addButton_onClicked(self):
        sl_obj = cmds.ls(selection=True, long=True)
        self.add_items_to_list(sl_obj)
        for item in sl_obj:
            self.save_material(item)

    # オブジェクトをリストに追加
    def add_items_to_list(self, items):
        if items:
            for item in items:
                short_name = cmds.ls(item, shortNames=True)[0]
                self.list.addItem(short_name)
                # ハイライト状態を初期化
                self.highlight_states[short_name] = False
        else:
            print("No objects in list selected")

    # removeButtonの関数
    def removeButton_onClicked(self):
        selected_items = self.list.selectedItems()
        self.remove_selected_items(selected_items)

    # select_enableの関数
    def select_enable(self):
        if self.select_enable_CheckBox.isChecked():
            cmds.select(clear=True)
            self.select_items_in_list()

    # refrshButtonの関数
    def refreshButton_onClicked(self):
        # リストをクリアする前に選択されているアイテムを取得
        selected_items = [item.text() for item in self.list.selectedItems()]
        self.list.clear()
        # クリアした後に選択状態を復元する
        self.add_items_to_list(selected_items)
        # 元のマテリアルに戻す
        for item_name in selected_items:
            self.restore_material(item_name)

    # 衝突判定
    def search_button_onClicked(self):
        try:
            selected_items = [item.text() for item in self.list.selectedItems()]
            if len(selected_items) > 1:
                dag_paths = []
                for item_name in selected_items:
                    dag_path, item_mesh_fn = self.get_dag_path_from_item(item_name)
                    if dag_path is not None and item_mesh_fn is not None:
                        dag_paths.append((dag_path, item_mesh_fn))
                sample_points = self.generate_sample_points(dag_paths)
                for dag_path, item_mesh_fn in dag_paths:
                    item_mesh_fn = om2.MFnMesh(dag_path)
                    self.sample_point_ray_cast(item_mesh_fn, sample_points, dag_path)
        except Exception as e:
            print(f"An error occurred in search_button_onClicked: {str(e)}")

    # 赤いマテリアルを作成
    def create_red_material(self):
        red_material_name = "redMaterial"
        if not cmds.objExists(red_material_name):
            shading_group_name = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="redShadingGroup")
            red_material_name = cmds.shadingNode('lambert', asShader=True, name=red_material_name)
            cmds.setAttr(red_material_name + '.color', 1, 0, 0, type="double3")
            # マテリアルをシェーディング グループに関連付け
            cmds.surfaceShaderList(red_material_name, add=shading_group_name)
        self.red_material_name = red_material_name

    # マテリアルを保存
    def save_material(self, item_name):
        # オブジェクトに割り当てられているマテリアルを取得
        shading_engine = cmds.listConnections(item_name, type='shadingEngine')
        if shading_engine:
            material = cmds.ls(cmds.listConnections(shading_engine), materials=True)
            if material:
                self.materials[item_name] = material[0]

    # マテリアルを復元
    def restore_material(self, item_name):
        if item_name in self.materials:
            material = self.materials[item_name]
            cmds.select(item_name, replace=True)
            cmds.hyperShade(assign=material)

    # 選択されたアイテムをリストから削除
    def remove_selected_items(self, selected_items):
        if selected_items:
            for item in selected_items:
                if item.text() in self.highlight_states:
                    del self.highlight_states[item.text()]
                self.list.takeItem(self.list.row(item))
            print(f"{len(selected_items)} items removed from the list")
        else:
            print("No objects in list selected")

    # リスト内のアイテムをMayaで選択状態にする
    def select_items_in_list(self, items=None):
        if not items:
            items = [self.list.item(i) for i in range(self.list.count())]
        for item in items:
            cmds.select(item.text(), add=True)

    # Info Editorを更新
    def update_info_editor(self, highlighted_faces_info):
        if self.text_editor:
            # ハイライトされたフェースをリセット
            for item_name in self.highlight_states:
                if self.highlight_states[item_name]:
                    self.restore_material(item_name)
                    self.highlight_states[item_name] = False
            if highlighted_faces_info:
                for info in highlighted_faces_info:
                    self.text_editor.appendPlainText(info)
        else:
            print("Error: 'text_editor' is None.")

    # ハイライトされたフェースの情報を取得
    def get_highlighted_faces_info(self, item_mesh_fn, face_indices):
        highlighted_faces_info = []
        for face_index in face_indices:
            vertex_indices = item_mesh_fn.getPolygonVertices(face_index)
            # MIntArrayをPythonのリストに変換
            vertex_indices_list = [vertex_indices[i] for i in range(len(vertex_indices))]
            # 文字列に変換
            info_str = f"Face Index {face_index}, Vertex Indices: {vertex_indices_list}"
            highlighted_faces_info.append(info_str)
        return highlighted_faces_info

    # 選択したオブジェクトのDagPathを取得する
    def get_dag_path_from_item(self, item_name):
        selection_list = om2.MSelectionList()
        try:
            selection_list.add(item_name)
        except RuntimeError:
            print(f"Error: Object {item_name} does not exist.")
            return None, None
        dag_path = om2.MDagPath()
        # トランスフォームノードからメッシュノードにアクセス
        if selection_list.length() > 0:
            try:
                dag_path = selection_list.getDagPath(0)
                dag_path.extendToShape()
            except RuntimeError:
                print(f"Error: Could not get DagPath for {item_name}.")
                return None, None
            # メッシュノードを指しているかをチェック
            if dag_path.apiType() == om2.MFn.kMesh:
                item_mesh_fn = om2.MFnMesh(dag_path)
                return dag_path, item_mesh_fn
            else:
                print(f"Error: {item_name} is not a mesh.")
                return None, None
        else:
            print(f"Error: Could not get DagPath for {item_name}.")
            return None, None

    # リストで選択するとMayaでも選択状態にする
    def list_selection_changed(self):
        selected_items = self.list.selectedItems()
        if self.select_enable_CheckBox.isChecked() and selected_items:
            cmds.select(clear=True)
            self.select_items_in_list(selected_items)

    # text_editorをクリックしたときの処理
    def toggle_text_editor(self):
        current_visibility = self.text_editor.isVisible()
        self.text_editor.setVisible(not current_visibility)
        if current_visibility:
            selected_items = self.list.selectedItems()
            self.update_info_editor(selected_items)

    # 複数のオブジェクトのメッシュの内部にあるサンプルポイントを生成
    def generate_sample_points(self, dag_paths):
        sample_points = []
        inside_point = []
        for i in range(len(dag_paths)):
            for j in range(i + 1, len(dag_paths)):
                dag_path1, item_mesh_fn1 = dag_paths[i]
                dag_path2, item_mesh_fn2 = dag_paths[j]
                points1 = item_mesh_fn1.getPoints(om2.MSpace.kWorld)
                points2 = item_mesh_fn2.getPoints(om2.MSpace.kWorld)
                # 他方のメッシュの内部に存在する頂点の取得
                self.point_inside_mesh(points1, points2, item_mesh_fn1, item_mesh_fn2, inside_point)
                # バウンディングボックス内のポイントを抽出
                self.point_inside_bouding_box(points1, points2, item_mesh_fn1, item_mesh_fn2, inside_point)

        # 重複を避けてランダムな2つの頂点を選択して中点を生成
        for i in range(len(inside_point) // 2):
            point1, point2 = random.sample(inside_point, 2)
            middle_point = om2.MVector((point1.x + point2.x) / 2, (point1.y + point2.y) / 2, (point1.z + point2.z) / 2)
            sample_points.append(middle_point)
        print(f"inside_point: {len(inside_point)}")
        return sample_points

    def point_inside_mesh(self, points1, points2, item_mesh_fn1, item_mesh_fn2, inside_point):
        # メッシュ1の各面の中心座標を計算し、レイキャストを行い、メッシュ2の内部にある頂点を取得
        for face_index in range(item_mesh_fn1.numPolygons):
            face_vertices = item_mesh_fn1.getPolygonVertices(face_index)
            face_center = om2.MPoint()
            for vertex_index in face_vertices:
                point = points1[vertex_index]
                face_center.x += point.x
                face_center.y += point.y
                face_center.z += point.z
            face_center.x /= len(face_vertices)
            face_center.y /= len(face_vertices)
            face_center.z /= len(face_vertices)

            # メッシュの法線方向を取得
            face_normal = item_mesh_fn1.getPolygonNormal(face_index, om2.MSpace.kWorld)

            # 面の法線方向に沿ってレイの開始点を内側に調整
            ray_origin = face_center + 0.001 * face_normal
            ray_origin_float = om2.MFloatPoint(ray_origin.x, ray_origin.y, ray_origin.z)
            ray_direction_float = om2.MFloatVector(-face_normal.x, -face_normal.y, -face_normal.z)

            intersections = item_mesh_fn2.allIntersections(
                ray_origin_float, ray_direction_float, om2.MSpace.kWorld, 99999, False
            )
            if intersections:
                num_intersections = len(intersections[0])
                # 交差回数が奇数の場合他方のメッシュ内部で衝突したとする
                if num_intersections % 2 != 0:
                    if face_center not in inside_point:
                        inside_point.append(face_center)

        # メッシュ2の各面の中心座標を計算し、レイキャストを行い、メッシュ1の内部にある頂点を取得
        for face_index in range(item_mesh_fn2.numPolygons):
            face_vertices = item_mesh_fn2.getPolygonVertices(face_index)
            face_center = om2.MPoint(0, 0, 0)
            for vertex_index in face_vertices:
                point = points1[vertex_index]
                face_center.x += point.x
                face_center.y += point.y
                face_center.z += point.z
            face_center.x /= len(face_vertices)
            face_center.y /= len(face_vertices)
            face_center.z /= len(face_vertices)

            # メッシュの法線方向を取得
            face_normal = item_mesh_fn2.getPolygonNormal(face_index, om2.MSpace.kWorld)

            # 面の法線方向に沿ってレイの開始点を内側に調整
            ray_origin = face_center + 0.001 * face_normal
            ray_origin_float = om2.MFloatPoint(ray_origin.x, ray_origin.y, ray_origin.z)
            ray_direction_float = om2.MFloatVector(-face_normal.x, -face_normal.y, -face_normal.z)

            intersections = item_mesh_fn1.allIntersections(
                ray_origin_float, ray_direction_float, om2.MSpace.kWorld, 99999, False
            )
            if intersections:
                num_intersections = len(intersections[0])
                # 交差回数が奇数の場合他方のメッシュ内部で衝突したとする
                if num_intersections % 2 != 0:
                    if face_center not in inside_point:
                        inside_point.append(face_center)

        # メッシュ1とメッシュ2の両方の境界ボックス内にある点を残す
        inside_point[:] = [
            point for point in inside_point
            if self.is_point_inside_bounding_box(point, item_mesh_fn1.boundingBox, item_mesh_fn2.boundingBox)
        ]


    def point_inside_bouding_box(self, points1, points2, item_mesh_fn1, item_mesh_fn2, inside_point):
        # メッシュ1の境界ボックスを取得
        bbox1 = item_mesh_fn1.boundingBox

        # メッシュ2の境界ボックスを取得
        bbox2 = item_mesh_fn2.boundingBox

        # メッシュ1とメッシュ2の両方の境界ボックス内にある点を残す
        inside_point[:] = [
            point for point in inside_point
            if self.is_point_inside_bounding_box(point, bbox1, bbox2)
        ]


    def is_point_inside_bounding_box(self, point, bbox1, bbox2):
        transformation_matrix = om2.MMatrix()
        # 境界ボックスの最小と最大の各座標値をワールド座標系に変換
        bbox1_min = bbox1.min * transformation_matrix
        bbox1_max = bbox1.max * transformation_matrix
        bbox2_min = bbox2.min * transformation_matrix
        bbox2_max = bbox2.max * transformation_matrix

        # ポイントが境界ボックス内にあるかどうかをチェック
        return (
            bbox1_min.x <= point.x <= bbox1_max.x
            and bbox1_min.y <= point.y <= bbox1_max.y
            and bbox1_min.z <= point.z <= bbox1_max.z
            and bbox2_min.x <= point.x <= bbox2_max.x
            and bbox2_min.y <= point.y <= bbox2_max.y
            and bbox2_min.z <= point.z <= bbox2_max.z
        )

    # レイの方向を取得する関数
    def get_ray_direction(self, direction_index):
        # 定義された方向のベクトルを取得
        directions = [
            om2.MFloatVector(0, -1, 0),
            om2.MFloatVector(0, 1, 0),
            om2.MFloatVector(-1, 0, 0),
            om2.MFloatVector(1, 0, 0),
            om2.MFloatVector(0, 0, -1),
            om2.MFloatVector(0, 0, 1)
        ]
        # 3D 方向ベクトルの正規化
        if direction_index < len(directions):
            directions[direction_index].normalize()
        return directions[direction_index]

    # 衝突判定を行う関数
    def sample_point_ray_cast(self, item_mesh_fn, sample_points, dag_path):
        try:
            for sample_point in sample_points:
                is_collision = False
                highlighted_faces = set()
                for i in range(6):
                    ray_direction = self.get_ray_direction(i)
                    ray_origin = om2.MFloatPoint(sample_point.x, sample_point.y, sample_point.z)
                    both_direction = False
                    intersection_result = item_mesh_fn.allIntersections(
                        ray_origin,
                        ray_direction,
                        om2.MSpace.kWorld,
                        99999,
                        both_direction
                    )
                    print(f"ray_origin: {ray_origin}")
                    print(f"ray_direction: {ray_direction}")
                    if intersection_result is not None:
                        _, _, hit_faces, _, _, _ = intersection_result
                        if hit_faces is not None and len(hit_faces) > 0:
                            is_collision = True
                            first_hit_face = hit_faces[0]
                            if first_hit_face not in highlighted_faces:
                                highlighted_faces.add(first_hit_face)
                        else:
                            pass
                    else:
                        pass

                if is_collision:
                    highlighted_faces_info = self.get_highlighted_faces_info(item_mesh_fn, highlighted_faces)
                    self.infoeditor.update_info_editor(highlighted_faces_info)
                    self.assign_red_material(item_mesh_fn, highlighted_faces)
                else:
                    self.infoeditor.update_info_editor([])

        except RuntimeError as e:
            print(f"サンプルポイントレイキャストでエラーが発生しました: {str(e)}")
        except Exception as e:
            print(f"予期しないエラーがサンプルポイントレイキャストで発生しました: {str(e)}")

    # 赤いマテリアルをアサイン
    def assign_red_material(self, item_mesh_fn, face_indices):
        # 赤いマテリアルを適用
        for face_index in face_indices:
            cmds.select(cl=True)
            vertex_indices = item_mesh_fn.getPolygonVertices(face_index)
            face_name = f"{item_mesh_fn.name()}.f[{face_index}]"
            cmds.select(face_name, add=True)
            cmds.hyperShade(assign=self.red_material_name)
            cmds.select(cl=True)
            for vertex_index in vertex_indices:
                cmds.select(f"{item_mesh_fn.name()}.vtx[{vertex_index}]", add=True)
            cmds.hilite(replace=True)

def get_maya_window():
    ptr = om.MQtUtil.mainWindow()
    widget = wrapInstance(int(ptr), QtWidgets.QWidget)
    return widget

def launch_from_maya():
    maya_window = get_maya_window()
    window = MainWindow(parent=maya_window)
    window.show()

launch_from_maya()