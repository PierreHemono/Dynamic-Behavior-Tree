#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import collections
import re
import rospy

# Définition de la knowledge_base
knowledge_base = {
    "OP11": {"pick_aruco_frame": 581, "place_aruco_frame": 584},
    "OP12": {"pick_aruco_frame": 582, "place_aruco_frame": 584},
    "OP13": {"pick_aruco_frame": 579, "place_aruco_frame": 584},
    "OP14": {"pick_aruco_frame": 578, "place_aruco_frame": 584},
    "OP15": {"pick_aruco_frame": 583, "place_aruco_frame": 582},
    "OP16": {"pick_aruco_frame": 578, "place_aruco_frame": 584},
    "OP21": {"pick_aruco_frame": 584, "place_aruco_frame": 585},
    "OP22": {"pick_aruco_frame": 582, "place_aruco_frame": 592},
    "OP23": {"pick_aruco_frame": 590, "place_aruco_frame": 590},
    "OP31": {"pick_aruco_frame": 584, "place_aruco_frame": 584},
    "OP32": {"pick_aruco_frame": 583, "place_aruco_frame": 582},
    "OP33": {"pick_aruco_frame": 578, "place_aruco_frame": 579},
    "OP41": {"pick_aruco_frame": 583, "place_aruco_frame": 584},
    "OP42": {"pick_aruco_frame": 583, "place_aruco_frame": 583},
    "OP43": {"pick_aruco_frame": 579, "place_aruco_frame": 579},
    "OP44": {"pick_aruco_frame": 578, "place_aruco_frame": 584},
    "OP45": {"pick_aruco_frame": 583, "place_aruco_frame": 582},
    "OP46": {"pick_aruco_frame": 578, "place_aruco_frame": 584},
}

# Définition de l'ordre des paramètres pour chaque prédicat (ordre complet)
ALL_PREDICATE_PARAMETER_ORDER = {
    "at": ["a", "l"],
    "tool_at": ["t", "l"],
    "holding": ["a", "t"],
    "wait_done": ["a"],
    "can_operate": ["t", "op"],
    # Les prédicats pick_opXX_done, place_opXX_done et move_to_<destination>_done seront ajoutés dynamiquement
}

# Mapping des localisations à leurs localisations opposées
opposite_location = {
    "loc_workstation": "loc_base",
    "loc_base": "loc_workstation",
    # Ajoutez d'autres mappings si nécessaire
}

def parse_pddl_plan(plan_file):
    actions = collections.OrderedDict()
    tools_in_plan = set()
    tool_to_op = {}
    pattern = r'^\s*(\d+\.\d+):\s*\(([\w-]+)([^)]*)\)\s*\[\d+\.\d+\]'
    with open(plan_file, 'r') as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith(';'):  # Ignorer les lignes vides et les commentaires
                continue
            match = re.match(pattern, line)
            if match:
                time = match.group(1)
                action_name = match.group(2).upper()
                params_str = match.group(3).strip()
                params = params_str.split()
                if not params:
                    rospy.logwarn("Aucun paramètre trouvé pour l'action : {}".format(line))
                    continue

                action_key = action_name + "_" + time.replace('.', '_')
                if "MOVE_TO" in action_name:
                    if len(params) != 3:
                        rospy.logerr("Nombre de paramètres incorrect pour MOVE_TO : {}".format(line))
                        continue
                    agent, from_location, to_location = params
                    actions[action_key] = {
                        "action": "move_to",
                        "agent": agent,
                        "from": from_location,
                        "to": to_location
                    }
                elif "PICK" in action_name or "PLACE" in action_name:
                    agent = params[0]
                    tool = params[1]
                    tools_in_plan.add(tool)
                    # Extraire l'opération complète (OPXX[_suffix]) à partir du nom de l'action ou du nom de l'outil
                    op_match = re.search(r'(OP\d{2}(?:_\w+)?)', action_name.upper())
                    if not op_match:
                        op_match = re.search(r'(OP\d{2}(?:_\w+)?)', tool.upper())
                    if op_match:
                        op_key = op_match.group(1)
                        tool_to_op[tool] = op_key
                    else:
                        rospy.logwarn("Impossible d'extraire OPXX du nom de l'action ou de l'outil '{}'".format(tool))
                        continue

                    if "PICK" in action_name and len(params) == 3:
                        location = params[2]
                    elif "PLACE" in action_name and len(params) == 3:
                        location = params[2]
                    else:
                        location = None
                    actions[action_key] = {
                        "action": "pick" if "PICK" in action_name else "place",
                        "agent": agent,
                        "tool": tool,
                        "location": location,
                        "op_key": op_key  # Ajouter op_key pour une utilisation ultérieure
                    }
                elif "WAIT" in action_name:
                    agent = params[0]
                    actions[action_key] = {
                        "action": "wait",
                        "agent": agent,
                        "duration": 10.0  # Ajustez la durée si nécessaire
                    }
                else:
                    rospy.logwarn("Action inconnue détectée : {}".format(action_name))
            else:
                # Ignorer les lignes qui ne correspondent pas au motif
                pass
    return actions, tool_to_op

def filter_actions(actions_dict):
    """
    Filtre les actions 'move_to' lorsque la localisation de départ et d'arrivée est la même.

    :param actions_dict: Dictionnaire des actions du plan initial.
    :return: Dictionnaire des actions filtrées.
    """
    filtered_actions = collections.OrderedDict()
    for key, action in actions_dict.items():
        if action['action'] == 'move_to':
            if action['from'] == action['to']:
                rospy.logdebug("Action 'move_to' ignorée car les localisations sont identiques: '{}' -> '{}'".format(
                    action['from'], action['to']))
                continue  # Ignorer cette action
        filtered_actions[key] = action
    return filtered_actions

def get_base_op_key(op_key):
    return op_key.split('_')[0]  # Retourne 'OP22' pour 'OP22_CO'

def create_behavior_tree_file(actions_dict, tool_to_op, output_file):
    # Collecter toutes les opérations uniques pour éviter les redéfinitions
    unique_operations = set(tool_to_op.values())
    used_predicates = set()

    # Mapping des localisations aux coordonnées (Mise à jour avec les coordonnées correctes)
    location_coordinates = {
        'loc_base': {'x': 0.147, 'y': -10.87, 'orientation_z': 0.99, 'orientation_w': 0.011},
        'loc_workstation': {'x': 0.325, 'y': -8.8, 'orientation_z': 0.99, 'orientation_w': 0.011},
        # Ajoutez d'autres localisations avec leurs coordonnées si nécessaire
    }

    # Mise à jour de ALL_PREDICATE_PARAMETER_ORDER avec les prédicats pick_opXX_done et place_opXX_done
    for op_key in unique_operations:
        predicate_pick_done = "pick_{}_done".format(op_key.lower())
        predicate_place_done = "place_{}_done".format(op_key.lower())
        ALL_PREDICATE_PARAMETER_ORDER[predicate_pick_done] = []
        ALL_PREDICATE_PARAMETER_ORDER[predicate_place_done] = []

    # Mise à jour de ALL_PREDICATE_PARAMETER_ORDER avec les prédicats move_to_<destination>_done
    for op_name, details in actions_dict.items():
        action_type = details["action"]
        if action_type == "move_to":
            destination = details['to']
            predicate_name_done = "move_to_{}_done".format(destination)
            ALL_PREDICATE_PARAMETER_ORDER[predicate_name_done] = []
            used_predicates.add("at")
            used_predicates.add(predicate_name_done)
        elif action_type in ["pick", "place"]:
            tool = details["tool"]
            op_key = details["op_key"]
            if op_key:
                if action_type == "pick":
                    used_predicates.add("holding")
                    used_predicates.add("tool_at")
                    predicate_pick_done = "pick_{}_done".format(op_key.lower())
                    used_predicates.add(predicate_pick_done)
                elif action_type == "place":
                    used_predicates.add("tool_at")
                    used_predicates.add("holding")
                    predicate_place_done = "place_{}_done".format(op_key.lower())
                    used_predicates.add(predicate_place_done)
            else:
                rospy.logwarn("Aucun mapping trouvé pour l'outil '{}'".format(tool))
        elif action_type == "wait":
            used_predicates.add("wait_done")

    with open(output_file, "w") as file:
        # Écriture de l'en-tête du fichier BT
        file.write("#!/usr/bin/env python\n")
        file.write("# -*- coding: utf-8 -*-\n\n")
        file.write("import rospy\n")
        file.write("import py_trees\n")
        file.write("import py_trees_ros\n\n")
        file.write("from PreGraspArmRightAction import PreGraspArmRightAction\n")
        file.write("from moveitArucoBT import moveitAruco\n")
        file.write("from RotateBeforeGraspBT import RotateBeforeGrasp\n")
        file.write("from ArmRightHomeBT import ArmRightHome\n")
        file.write("from ObserveTableAction import ObserveTableAction  # Votre classe pour bouger la tête\n")
        file.write("from CheckArucoDetected import CheckArucoDetected\n")
        file.write("from CloseGripperRightBT import CloseGripperRight\n")
        file.write("from OpenGripperRightBT import OpenGripperRight\n")
        file.write("from MoveBaseGoalAction import MoveBaseGoalAction\n")
        file.write("from FinalGraspBT import FinalGrasp\n")
        file.write("from WaitAction import WaitAction  # Votre classe pour l'action wait\n")
        file.write("from LookForwardAndRaise import LookForwardAndRaise\n")  # Ajout de l'import
        file.write("from rosplan_knowledge_msgs.srv import KnowledgeUpdateService, KnowledgeUpdateServiceRequest\n")
        file.write("from rosplan_knowledge_msgs.msg import KnowledgeItem\n")
        file.write("from diagnostic_msgs.msg import KeyValue\n")
        file.write("from std_srvs.srv import Empty\n\n")

        # Définition de PREDICATE_PARAMETER_ORDER avec uniquement les prédicats utilisés
        file.write("# ===========================\n")
        file.write("# Définition de l'ordre des paramètres pour chaque prédicat utilisé\n")
        file.write("# ===========================\n\n")
        file.write("PREDICATE_PARAMETER_ORDER = {\n")
        for predicate in used_predicates:
            if predicate in ALL_PREDICATE_PARAMETER_ORDER:
                params = ALL_PREDICATE_PARAMETER_ORDER[predicate]
                file.write("    \"{0}\": {1},\n".format(predicate, params))
            else:
                rospy.logdebug("Prédicat '{}' non défini dans ALL_PREDICATE_PARAMETER_ORDER. Ignoré.".format(predicate))
        file.write("}\n\n")

        # ==================================
        # Fonction de mise à jour de la KB
        # ==================================
        file.write("# ===========================\n")
        file.write("# Fonction de mise à jour de la KB\n")
        file.write("# ===========================\n\n")
        file.write("def update_kb(predicate_name, parameters, add=True):\n")
        file.write("    rospy.logdebug(\"Mise à jour KB - Prédicat: '{}' | Params: {} | Ajout: {}\".format(predicate_name, parameters, add))\n")
        file.write("    service_name = '/rosplan_knowledge_base/update'\n")
        file.write("    try:\n")
        file.write("        rospy.wait_for_service(service_name, timeout=5)\n")
        file.write("        update_kb_client = rospy.ServiceProxy(service_name, KnowledgeUpdateService)\n")
        file.write("        request = KnowledgeUpdateServiceRequest()\n")
        file.write("        knowledge = KnowledgeItem()\n")
        file.write("        knowledge.knowledge_type = KnowledgeItem.FACT\n")
        file.write("        knowledge.attribute_name = predicate_name.strip()\n")
        file.write("        knowledge.is_negative = False\n")
        file.write("        if parameters:\n")
        file.write("            parameter_order = PREDICATE_PARAMETER_ORDER.get(predicate_name.strip())\n")
        file.write("            if parameter_order:\n")
        file.write("                missing_params = [p for p in parameter_order if p not in parameters]\n")
        file.write("                if missing_params:\n")
        file.write("                    rospy.logerr(\"Paramètres manquants pour le prédicat '{}': {}\".format(predicate_name, missing_params))\n")
        file.write("                    return\n")
        file.write("                knowledge.values = [KeyValue(key=k, value=parameters[k]) for k in parameter_order]\n")
        file.write("            else:\n")
        file.write("                rospy.logdebug(\"Ordre des paramètres non défini pour le prédicat '{}'. Utilisation de l'ordre par défaut.\".format(predicate_name))\n")
        file.write("                knowledge.values = [KeyValue(key=k, value=v) for k, v in parameters.items()]\n")
        file.write("        else:\n")
        file.write("            knowledge.values = []\n")
        file.write("        request.knowledge = knowledge\n")
        file.write("        request.update_type = KnowledgeUpdateServiceRequest.ADD_KNOWLEDGE if add else KnowledgeUpdateServiceRequest.REMOVE_KNOWLEDGE\n")
        file.write("        rospy.logdebug(\"Envoi de la requête à la KB: {}\".format(request))\n")
        file.write("        response = update_kb_client(request)\n")
        file.write("        if response.success:\n")
        file.write("            rospy.logdebug('KB mise à jour : {} avec {}'.format(predicate_name, parameters))\n")
        file.write("        else:\n")
        file.write("            rospy.logerr('Échec de la mise à jour de la KB pour le prédicat {}'.format(predicate_name))\n")
        file.write("    except rospy.ServiceException as e:\n")
        file.write("        rospy.logerr('Erreur lors de l\\'appel au service : {}'.format(e))\n")
        file.write("    except rospy.ROSException:\n")
        file.write("        rospy.logerr('Timeout lors de l\\'attente du service {}'.format(service_name))\n\n")

        # ==================================
        # Décorateur KBUpdateDecorator
        # ==================================
        file.write("# ==================================\n")
        file.write("# Décorateur KBUpdateDecorator\n")
        file.write("# ==================================\n\n")
        file.write("class KBUpdateDecorator(py_trees.decorators.Decorator):\n")
        file.write("    def __init__(self, name, on_success_predicates=[], on_failure_remove_predicates=[], on_success_remove_predicates=[], on_failure_predicates=[], child=None):\n")
        file.write("        super(KBUpdateDecorator, self).__init__(name=name, child=child)\n")
        file.write("        self.on_success_predicates = on_success_predicates\n")
        file.write("        self.on_failure_remove_predicates = on_failure_remove_predicates\n")
        file.write("        self.on_success_remove_predicates = on_success_remove_predicates\n")
        file.write("        self.on_failure_predicates = on_failure_predicates\n")
        file.write("\n")
        file.write("    def update(self):\n")
        file.write("        child_status = self.decorated.status\n")
        file.write("\n")
        file.write("        if child_status == py_trees.common.Status.SUCCESS:\n")
        file.write("            rospy.logdebug(\"[KBUpdateDecorator] '{}' succeeded. Updating KB...\".format(self.name))\n")
        file.write("            for predicate_name, parameters in self.on_success_predicates:\n")
        file.write("                update_kb(predicate_name, parameters, add=True)\n")
        file.write("            for predicate_name, parameters in self.on_success_remove_predicates:\n")
        file.write("                update_kb(predicate_name, parameters, add=False)\n")
        file.write("            return py_trees.common.Status.SUCCESS\n")
        file.write("\n")
        file.write("        elif child_status == py_trees.common.Status.FAILURE:\n")
        file.write("            rospy.logdebug(\"[KBUpdateDecorator] '{}' failed. Updating KB...\".format(self.name))\n")
        file.write("            for predicate_name, parameters in self.on_failure_remove_predicates:\n")
        file.write("                update_kb(predicate_name, parameters, add=False)\n")
        file.write("            for predicate_name, parameters in self.on_failure_predicates:\n")
        file.write("                update_kb(predicate_name, parameters, add=True)\n")
        file.write("            return py_trees.common.Status.FAILURE\n")
        file.write("\n")
        file.write("        else:\n")
        file.write("            return child_status\n\n")

        # ==================================
        # Création du Behavior Tree avec Décorateurs
        # ==================================
        file.write("# ==================================\n")
        file.write("# Création du Behavior Tree avec Décorateurs\n")
        file.write("# ==================================\n\n")
        file.write("def create_behavior_tree():\n")
        file.write("    # Séquence principale (racine)\n")
        file.write("    root = py_trees.composites.Sequence(\"RootSequence\")\n\n")

        # Mapping des marker IDs aux noms de topics
        file.write("    # Mapping des marker IDs aux noms de topics\n")
        file.write("    marker_id_to_topic = {\n")
        marker_id_to_topic = {
            581: "/aruco_single_581/pose",
            582: "/aruco_single_582/pose",
            583: "/aruco_single_583/pose",
            584: "/aruco_single_584/pose",
            585: "/arucotableau1/pose",
            586: "/arucotableau2/pose",
            587: "/arucotableau3/pose",
            588: "/arucotableau4/pose",
            589: "/arucotableau5/pose",
            590: "/arucotableau6/pose",
            591: "/arucotableau7/pose",
            592: "/arucotableau8/pose",
            578: "/aruco_single_578/pose",
            579: "/aruco_single_579/pose",
            # Ajoutez d'autres mappings si nécessaire
        }
        for marker_id, topic_name in marker_id_to_topic.items():
            file.write("        {}: \"{}\",\n".format(marker_id, topic_name))
        file.write("    }\n\n")

        # Définir toutes les variables marker_id_pick_OPXX et marker_id_place_OPXX une seule fois
        for op_key in unique_operations:
            base_op_key = get_base_op_key(op_key)
            if base_op_key in knowledge_base:
                pick_marker_id = knowledge_base.get(base_op_key, {}).get('pick_aruco_frame', 0)
                place_marker_id = knowledge_base.get(base_op_key, {}).get('place_aruco_frame', 0)
            else:
                rospy.logwarn("L'opération '{}' n'est pas dans knowledge_base. Utilisation des valeurs par défaut pour les marker IDs.".format(op_key))
                pick_marker_id = 0  # Valeur par défaut
                place_marker_id = 0
            file.write("    marker_id_pick_{0} = {1}\n".format(op_key, pick_marker_id))
            file.write("    marker_id_place_{0} = {1}\n".format(op_key, place_marker_id))
        file.write("\n")

        # Initialiser la liste des décorateurs ici
        file.write("    # Initialiser la liste des décorateurs\n")
        file.write("    decorators = []\n\n")

        # Nous allons également garder une liste des noms de décorateurs pour l'ajout à la racine
        decorator_names = []

        # Définir toutes les séquences et décorateurs à l'intérieur de la fonction
        for op_name, details in actions_dict.items():
            action_type = details["action"]  # "pick", "place", "move_to", "wait"

            if action_type == "move_to":
                # Génération des séquences de mouvement
                file.write("    # Séquence de mouvement pour {0}\n".format(op_name))
                move_sequence_name = "MoveSequence_{0}".format(op_name)
                file.write("    {0} = py_trees.composites.Sequence(\"{0}\")\n".format(move_sequence_name))
                coordinates = location_coordinates.get(details['to'])
                if coordinates:
                    file.write("    move_base_goal = MoveBaseGoalAction(\"Move to {0}\", x={1}, y={2}, orientation_z={3}, orientation_w={4})\n".format(
                        details['to'], coordinates['x'], coordinates['y'], coordinates['orientation_z'], coordinates['orientation_w']))
                else:
                    rospy.logerr("Coordonnées non définies pour la localisation '{}'".format(details['to']))
                    continue
                file.write("    {0}.add_child(move_base_goal)\n\n".format(move_sequence_name))

                # Générer le prédicat dynamique pour move_to
                predicate_name_done = "move_to_{}_done".format(details['to'])

                # Générer le décorateur pour move_to
                move_decorator_name = "MoveDecorator_{0}".format(op_name)
                file.write("    {0} = KBUpdateDecorator(\n".format(move_decorator_name))
                file.write("        name=\"{0}\",\n".format(move_decorator_name))
                file.write("        on_success_predicates=[('at', {{'a': '{0}', 'l': '{1}'}}), ('{2}', {{}})],\n".format(details['agent'], details['to'], predicate_name_done))
                file.write("        on_success_remove_predicates=[('at', {{'a': '{0}', 'l': '{1}'}})],\n".format(details['agent'], details['from']))
                file.write("        child={0}\n".format(move_sequence_name))
                file.write("    )\n\n")
                file.write("    decorators.append({0})\n\n".format(move_decorator_name))
                decorator_names.append(move_decorator_name)

            elif action_type == "wait":
                # Générer la séquence de wait
                file.write("    # Séquence de wait pour {0}\n".format(op_name))
                wait_sequence_name = "WaitSequence_{0}".format(op_name)
                file.write("    {0} = py_trees.composites.Sequence(\"{0}\")\n".format(wait_sequence_name))
                duration = details.get("duration", 10.0)  # Durée par défaut de 10.0 secondes
                file.write("    wait_action = WaitAction(\"WaitAction_{0}\", duration={1})\n".format(op_name, duration))
                file.write("    {0}.add_child(wait_action)\n\n".format(wait_sequence_name))

                # Générer le décorateur pour wait
                wait_decorator_name = "WaitDecorator_{0}".format(op_name)
                file.write("    {0} = KBUpdateDecorator(\n".format(wait_decorator_name))
                file.write("        name=\"{0}\",\n".format(wait_decorator_name))
                file.write("        on_success_predicates=[('wait_done', {{'a': '{0}'}})],\n".format(details["agent"]))
                file.write("        child={0}\n".format(wait_sequence_name))
                file.write("    )\n\n")
                file.write("    decorators.append({0})\n\n".format(wait_decorator_name))
                decorator_names.append(wait_decorator_name)

            elif action_type in ["pick", "place"]:
                tool = details["tool"]
                op_key = details["op_key"]
                base_op_key = get_base_op_key(op_key)
                if not op_key:
                    rospy.logwarn("Aucun mapping trouvé pour l'outil '{}'".format(tool))
                    continue

                if action_type == "pick":
                    marker_id_var = "marker_id_pick_{0}".format(op_key)
                    predicate_name_done = "pick_{0}_done".format(op_key.lower())
                    predicate_name = "holding"
                    predicate_params = {"a": details["agent"], "t": details["tool"]}
                    predicate_remove = ("tool_at", {"t": details["tool"], "l": details["location"]})
                    # Déterminer la localisation opposée
                    original_location = details["location"]
                    opposite_loc = opposite_location.get(original_location, None)
                    if opposite_loc is None:
                        rospy.logerr("Localisation opposée non définie pour '{}'".format(original_location))
                        opposite_loc = "loc_base"  # Valeur par défaut
                else:  # place
                    marker_id_var = "marker_id_place_{0}".format(op_key)
                    predicate_name_done = "place_{0}_done".format(op_key.lower())
                    predicate_name = "tool_at"
                    # Pour l'action place, la localisation est celle spécifiée dans l'action
                    # Si la localisation n'est pas spécifiée, on utilise 'loc_workstation' par défaut
                    location = details.get("location", "loc_workstation")
                    predicate_params = {"t": details["tool"], "l": location}
                    predicate_remove = ("holding", {"a": details["agent"], "t": details["tool"]})
                    # Déterminer la localisation opposée
                    original_location = location
                    opposite_loc = opposite_location.get(original_location, None)
                    if opposite_loc is None:
                        rospy.logerr("Localisation opposée non définie pour '{}'".format(original_location))
                        opposite_loc = "loc_base"  # Valeur par défaut

                if action_type == "pick":
                    # Récupérer le marker_id et le topic_name pour le marqueur à détecter
                    marker_id = knowledge_base.get(base_op_key, {}).get('pick_aruco_frame', 0)
                    topic_name = marker_id_to_topic.get(marker_id, "/aruco_single_1/pose")  # Valeur par défaut

                    # Générer la séquence de pick
                    file.write("    # Séquence de pick pour {0}\n".format(op_name))
                    pick_sequence_name = "PickSequence_{0}".format(op_name)
                    file.write("    {0} = py_trees.composites.Sequence(\"{0}\")\n".format(pick_sequence_name))
                    file.write("    detection_selector = py_trees.composites.Selector(\"DetectionSelector_{0}\")\n".format(op_name))
                    file.write("    check_aruco = CheckArucoDetected(name=\"CheckAruco_{0}\", topic_name=\"{1}\", timeout=2.0)\n".format(op_name, topic_name))
                    file.write("    observe_and_check = py_trees.composites.Sequence(\"ObserveAndCheck_{0}\")\n".format(op_name))
                    file.write("    observe_table_action = ObserveTableAction(\"ObserveTableAction_{0}\")\n".format(op_name))
                    file.write("    check_aruco_again = CheckArucoDetected(\"CheckAruco_{0}_Again\", topic_name=\"{1}\", timeout=2.0)\n".format(op_name, topic_name))
                    file.write("    observe_and_check.add_children([observe_table_action, check_aruco_again])\n")
                    file.write("    detection_selector.add_children([check_aruco, observe_and_check])\n")
                    file.write("    {0}.add_child(detection_selector)\n".format(pick_sequence_name))
                    file.write("    {0}.add_children([\n".format(pick_sequence_name))
                    file.write("        PreGraspArmRightAction(\"PreGraspArmRight_{0}\"),\n".format(op_name))
                    file.write("        moveitAruco(\"MoveItAruco_{0}\", {1}),\n".format(op_name, marker_id_var))
                    file.write("        RotateBeforeGrasp(\"RotateBeforeGrasp_{0}\"),\n".format(op_name))
                    file.write("        FinalGrasp(\"FinalGrasp_{0}\"),\n".format(op_name))
                    file.write("        CloseGripperRight(\"CloseGripperRight_{0}\"),\n".format(op_name))
                    file.write("        ArmRightHome(\"ArmRightHome_{0}\"),\n".format(op_name))
                    file.write("        LookForwardAndRaise(\"LookForwardAndRaise_{0}\")\n".format(op_name))
                    file.write("    ])\n\n")

                    # Générer le décorateur pour pick avec les on_failure_predicates et on_failure_remove_predicates
                    pick_decorator_name = "PickDecorator_{0}".format(op_name)
                    file.write("    {0} = KBUpdateDecorator(\n".format(pick_decorator_name))
                    file.write("        name=\"{0}\",\n".format(pick_decorator_name))
                    file.write("        on_success_predicates=[('holding', {{'a': '{0}', 't': '{1}'}}), ('{2}', {{}})],\n".format(
                        predicate_params["a"], predicate_params["t"], predicate_name_done))
                    # Ajout des on_failure_predicates et on_failure_remove_predicates
                    file.write("        on_failure_predicates=[('tool_at', {{'t': '{0}', 'l': '{1}'}})],\n".format(
                        details["tool"], opposite_loc))
                    file.write("        on_failure_remove_predicates=[('tool_at', {{'t': '{0}', 'l': '{1}'}})],\n".format(
                        details["tool"], original_location))
                    file.write("        child={0}\n".format(pick_sequence_name))
                    file.write("    )\n\n")
                    file.write("    decorators.append({0})\n\n".format(pick_decorator_name))
                    decorator_names.append(pick_decorator_name)

                elif action_type == "place":
                    # Récupérer le marker_id et le topic_name pour le marqueur à détecter
                    marker_id = knowledge_base.get(base_op_key, {}).get('place_aruco_frame', 0)
                    topic_name = marker_id_to_topic.get(marker_id, "/aruco_single_1/pose")  # Valeur par défaut

                    # Générer la séquence de place
                    file.write("    # Séquence de place pour {0}\n".format(op_name))
                    place_sequence_name = "PlaceSequence_{0}".format(op_name)
                    file.write("    {0} = py_trees.composites.Sequence(\"{0}\")\n".format(place_sequence_name))
                    file.write("    {0}.add_children([\n".format(place_sequence_name))
                    file.write("        moveitAruco(\"MoveItPlace_{0}\", {1}),\n".format(op_name, marker_id_var))
                    file.write("        OpenGripperRight(\"OpenGripperRight_{0}\"),\n".format(op_name))
                    file.write("        ArmRightHome(\"ArmRightHome_{0}\"),\n".format(op_name))
                    file.write("        LookForwardAndRaise(\"LookForwardAndRaise_{0}\")\n".format(op_name))
                    file.write("    ])\n\n")

                    # Générer le décorateur pour place avec les on_failure_predicates et on_failure_remove_predicates
                    place_decorator_name = "PlaceDecorator_{0}".format(op_name)
                    file.write("    {0} = KBUpdateDecorator(\n".format(place_decorator_name))
                    file.write("        name=\"{0}\",\n".format(place_decorator_name))
                    file.write("        on_success_predicates=[('tool_at', {{'t': '{0}', 'l': '{1}'}}), ('{2}', {{}})],\n".format(
                        predicate_params["t"], location, predicate_name_done))
                    file.write("        on_success_remove_predicates=[('holding', {{'a': '{0}', 't': '{1}'}})],\n".format(
                        predicate_remove[1]["a"], predicate_remove[1]["t"]))
                    # Ajout des on_failure_predicates et on_failure_remove_predicates
                    file.write("        on_failure_predicates=[('holding', {{'a': '{0}', 't': '{1}'}})],\n".format(
                        details["agent"], details["tool"]))
                    file.write("        on_failure_remove_predicates=[('tool_at', {{'t': '{0}', 'l': '{1}'}})],\n".format(
                        details["tool"], original_location))
                    file.write("        child={0}\n".format(place_sequence_name))
                    file.write("    )\n\n")
                    file.write("    decorators.append({0})\n\n".format(place_decorator_name))
                    decorator_names.append(place_decorator_name)

        # Ajouter tous les décorateurs au root dans l'ordre
        file.write("    # Ajouter les décorateurs au root\n")
        file.write("    root.add_children([\n")
        for decorator_name in decorator_names:
            file.write("        {},\n".format(decorator_name))
        file.write("    ])\n\n")
        file.write("    return root\n\n")

        # ==================================
        # Fonction principale
        # ==================================
        file.write("# ==================================\n")
        file.write("# Boucle principale\n")
        file.write("# ==================================\n\n")
        file.write("def main():\n")
        file.write("    rospy.init_node('behavior_tree_tiago', anonymous=True, log_level=rospy.INFO)\n\n")
        file.write("    # Créer le Behavior Tree\n")
        file.write("    bt_root = create_behavior_tree()\n")
        file.write("    bt = py_trees_ros.trees.BehaviourTree(bt_root)\n\n")
        file.write("    # Afficher l'arbre en ASCII\n")
        file.write("    tree_ascii = py_trees.display.ascii_tree(bt.root)\n")
        file.write("    rospy.loginfo(\"\\n\" + tree_ascii)\n\n")
        file.write("    # Configurer l'arbre\n")
        file.write("    bt.setup(timeout=15)\n\n")
        file.write("    rospy.loginfo('Lancement de l\\'arbre de comportements')\n\n")
        file.write("    # Boucle principale\n")
        file.write("    rate = rospy.Rate(10)\n")
        file.write("    while not rospy.is_shutdown():\n")
        file.write("        bt.tick()\n")
        file.write("        tree_status = bt.root.status\n\n")
        file.write("        if tree_status == py_trees.common.Status.RUNNING:\n")
        file.write("            rospy.loginfo('Behavior Tree en cours d\\'exécution...')\n")
        file.write("        elif tree_status == py_trees.common.Status.FAILURE:\n")
        file.write("            rospy.loginfo('Behavior Tree terminé avec statut : FAILURE')\n")
        file.write("            break  # Arrêter la boucle en cas de FAILURE\n")
        file.write("        elif tree_status == py_trees.common.Status.SUCCESS:\n")
        file.write("            rospy.loginfo('Behavior Tree terminé avec statut : SUCCESS')\n")
        file.write("            break  # Arrêter la boucle en cas de SUCCESS\n")
        file.write("        rate.sleep()\n\n")
        file.write("if __name__ == '__main__':\n")
        file.write("    main()\n")

def main():
    plan_file = "/home/admin-local/eXoBot_ws/src/rosplan_demos/rosplan_demos/common/plan.pddl"
    actions_dict, tool_to_op = parse_pddl_plan(plan_file)
    actions_dict = filter_actions(actions_dict)  # Ajout du filtrage des actions
    output_file = "/home/admin-local/tiago_dual_public_ws/src/my_tiago_project/scripts/behavior_tree_autoV2.py"
    create_behavior_tree_file(actions_dict, tool_to_op, output_file)
    print("Behavior Tree file '{0}' generated successfully.".format(output_file))

if __name__ == "__main__":
    main()
